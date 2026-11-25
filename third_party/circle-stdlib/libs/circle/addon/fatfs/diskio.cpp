/*-----------------------------------------------------------------------*/
/* Low level disk I/O module skeleton for FatFs     (C)ChaN, 2019        */
/* Implementation for Circle by R. Stange <rsta2@o2online.de>            */
/*-----------------------------------------------------------------------*/
/* If a working storage control module is available, it should be        */
/* attached to the FatFs via a glue function rather than modifying it.   */
/* This is an example of glue functions to attach various exsisting      */
/* storage control modules to the FatFs module with a defined API.       */
/*-----------------------------------------------------------------------*/

#include "ff.h"			/* Obtains integer types */
#include "diskio.h"		/* Declarations of disk functions */
#include <circle/device.h>
#include <circle/devicenameservice.h>
#include <circle/util.h>
#include <circle/types.h>
#include <circle/genericlock.h>
#include <circle/synchronize.h>
#include <assert.h>

#if FF_MIN_SS != FF_MAX_SS
	#error FF_MIN_SS != FF_MAX_SS is not supported!
#endif
#define SECTOR_SIZE		FF_MIN_SS

/*-----------------------------------------------------------------------*/
/* Static Data                                                           */
/*-----------------------------------------------------------------------*/

static const char *s_pVolumeName[FF_VOLUMES] =
{
	"emmc1",
	"emmc2",
	"umsd1",
	"umsd2",
	"umsd3",
	"ufd1",
	"nvme1"
};

static CDevice *s_pVolume[FF_VOLUMES] = {0};

// Each physical slot owns its buffer and Seek+transfer transaction. These
// locks do not pin CDevice objects: removal/mount lifetime remains unchanged.
#define TRANSFER_BUFFER_SIZE (32U * 1024U)
#if TRANSFER_BUFFER_SIZE % FF_MAX_SS != 0
#error Transfer buffer must contain whole sectors
#endif
static u8 s_TransferBuffer[FF_VOLUMES][TRANSFER_BUFFER_SIZE] CACHE_ALIGN;
static CGenericLock s_TransferLock[FF_VOLUMES];

class CDiskTransaction
{
public:
 explicit CDiskTransaction (BYTE drive) : m_Lock (s_TransferLock[drive]) { m_Lock.Acquire (); }
 ~CDiskTransaction (void) { m_Lock.Release (); }
private:
 CGenericLock &m_Lock;
};



/*-----------------------------------------------------------------------*/
/* Callbacks                                                             */
/*-----------------------------------------------------------------------*/

static void disk_removed (
	CDevice *pDevice,	/* device removed */
	void *pContext
)
{
	*((CDevice **) pContext) = 0;
}



/*-----------------------------------------------------------------------*/
/* Get Drive Status                                                      */
/*-----------------------------------------------------------------------*/

DSTATUS disk_status (
	BYTE pdrv		/* Physical drive nmuber to identify the drive */
)
{
	if (   pdrv < FF_VOLUMES
	    && s_pVolume[pdrv] != 0)
	{
		return 0;
	}

	return STA_NOINIT;
}



/*-----------------------------------------------------------------------*/
/* Inidialize a Drive                                                    */
/*-----------------------------------------------------------------------*/

DSTATUS disk_initialize (
	BYTE pdrv				/* Physical drive nmuber to identify the drive */
)
{
	if (pdrv >= FF_VOLUMES)
	{
		return STA_NOINIT;
	}

	s_pVolume[pdrv] = CDeviceNameService::Get ()->GetDevice (s_pVolumeName[pdrv], TRUE);
	if (s_pVolume[pdrv] != 0)
	{
		s_pVolume[pdrv]->RegisterRemovedHandler (disk_removed, &s_pVolume[pdrv]);

		return 0;
	}

	return STA_NOINIT;
}



/*-----------------------------------------------------------------------*/
/* Read Sector(s)                                                        */
/*-----------------------------------------------------------------------*/

// FatFs holds its volume lock before entering here. Keep IRQs enabled
// (TASK_LEVEL), and never yield or call mount/removal while this lock is held.
static DRESULT disk_transfer (BYTE pdrv, BYTE *buff, LBA_t sector, UINT count,
                             boolean write)
{
 if (pdrv >= FF_VOLUMES || buff == 0 || count == 0) return RES_PARERR;
 const QWORD max = (QWORD) -1;
 const QWORD lastLBA = (LBA_t) -1;
 if ((QWORD) count - 1 > lastLBA - (QWORD) sector
     || (QWORD) sector > max / SECTOR_SIZE
     || (QWORD) count > max / SECTOR_SIZE) return RES_PARERR;
 const QWORD bytes = (QWORD) count * SECTOR_SIZE;
 QWORD offset = (QWORD) sector * SECTOR_SIZE;
 // The request must also fit the caller's address space and byte offsets.
 if (bytes > (QWORD) (uintptr) -1
     || bytes > (QWORD) ((uintptr) -1 - (uintptr) buff)
     || offset > max - bytes) return RES_PARERR;

 CDiskTransaction transaction (pdrv);
 CDevice *pDevice = s_pVolume[pdrv];
 if (pDevice == 0) return RES_NOTRDY;
 const QWORD size = pDevice->GetSize ();
 if (size != max && (offset > size || bytes > size - offset)) return RES_PARERR;

 QWORD remaining = bytes;
 while (remaining != 0)
 {
  const unsigned length = remaining > TRANSFER_BUFFER_SIZE
                        ? TRANSFER_BUFFER_SIZE : (unsigned) remaining;
  BYTE *buffer = IS_CACHE_ALIGNED (buff, length) ? buff : s_TransferBuffer[pdrv];
  if (write && buffer != buff) memcpy (buffer, buff, length);
  if (pDevice->Seek (offset) != offset) return RES_ERROR;
  int transferred;
#if FF_FS_READONLY == 0
  if (write) transferred = pDevice->Write (buffer, length);
  else
#endif
  transferred = pDevice->Read (buffer, length);
  if (transferred != (int) length) return RES_ERROR;
  if (!write && buffer != buff) memcpy (buff, buffer, length);
  remaining -= length;
  offset += length;
  buff += length;
 }
 return RES_OK;
}

DRESULT disk_read (BYTE pdrv, BYTE *buff, LBA_t sector, UINT count)
{
 return disk_transfer (pdrv, buff, sector, count, FALSE);
}

#if FF_FS_READONLY == 0
DRESULT disk_write (BYTE pdrv, const BYTE *buff, LBA_t sector, UINT count)
{
 return disk_transfer (pdrv, const_cast<BYTE *> (buff), sector, count, TRUE);
}
#endif


/*-----------------------------------------------------------------------*/
/* Miscellaneous Functions                                               */
/*-----------------------------------------------------------------------*/

DRESULT disk_ioctl (
	BYTE pdrv,		/* Physical drive nmuber (0..) */
	BYTE cmd,		/* Control code */
	void *buff		/* Buffer to send/receive control data */
)
{
	switch (cmd)
	{
	case GET_SECTOR_COUNT:
		{
			if (pdrv >= FF_VOLUMES)
			{
				return RES_PARERR;
			}

			CDevice *pDevice =
				CDeviceNameService::Get ()->GetDevice (s_pVolumeName[pdrv], TRUE);
			if (pDevice != 0)
			{
				u64 ullSize = pDevice->GetSize ();
				if (ullSize == (u64) -1)
				{
					return RES_PARERR;
				}

				*(LBA_t *) buff = (LBA_t) (ullSize / SECTOR_SIZE);
			}
			else
			{
				return RES_NOTRDY;
			}
		}
		return RES_OK;

	case CTRL_SYNC:
		{
			if (pdrv >= FF_VOLUMES)
			{
				return RES_PARERR;
			}

			CDevice *pDevice =
				CDeviceNameService::Get ()->GetDevice (s_pVolumeName[pdrv], TRUE);
			if (pDevice != 0)
			{
				/* This fails, if unsupported, so ignore eventual errors. */
				pDevice->IOCtl (DEVICE_IOCTL_SYNC, 0);
			}
			else
			{
				return RES_NOTRDY;
			}
		}
		return RES_OK;

	case GET_SECTOR_SIZE:
		assert (buff != 0);
		*(WORD *) buff = SECTOR_SIZE;
		return RES_OK;

	case CTRL_EJECT:
		if (pdrv >= FF_VOLUMES)
		{
			return RES_PARERR;
		}

		if (s_pVolume[pdrv] == 0)
		{
			s_pVolume[pdrv] = CDeviceNameService::Get ()->GetDevice (s_pVolumeName[pdrv], TRUE);
			if (s_pVolume[pdrv] == 0)
			{
				return RES_NOTRDY;
			}
		}

		if (!s_pVolume[pdrv]->RemoveDevice ())
		{
			return RES_ERROR;
		}

		s_pVolume[pdrv] = 0;

		return RES_OK;
	}

	return RES_PARERR;
}

