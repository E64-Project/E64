//
// usbserialhost.cpp
//
// Circle - A C++ bare metal environment for Raspberry Pi
// Copyright (C) 2020  H. Kocevar <hinxx@protonmail.com>
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
#include <circle/synchronize.h>
#include <circle/util.h>
#include <circle/usb/usbserialhost.h>
#include <circle/usb/usbhostcontroller.h>
#include <circle/usb/usbrequest.h>
#include <circle/logger.h>
#include <assert.h>

LOGMODULE ("userialhost");

// Kept alive by the owner and by each submitted URB. A late completion
// after unplug cannot call a deleted serial function or reuse its DMA memory.
struct TUSBSerialAsyncState
{
	unsigned References = 1;
	CUSBEndpoint *In;
	CUSBEndpoint *Out;
	unsigned Header;
	unsigned PacketSize;
	boolean Input = FALSE;
	boolean Pending = FALSE;
	unsigned Complete = 0;
	int Result = -1;
	// Align inside ordinary heap storage, avoiding an over-aligned new ABI.
	u8 Storage[127];
	u8 *Buffer;

	TUSBSerialAsyncState (CUSBEndpoint *in, CUSBEndpoint *out, unsigned header)
	: In(in), Out(out), Header(header), PacketSize(in->GetMaxPacketSize ()),
	  Buffer(reinterpret_cast<u8 *> (((uintptr) Storage + 63) & ~(uintptr) 63)) {}
	~TUSBSerialAsyncState () { delete In; delete Out; }
	void Release ()
	{
		if (__atomic_sub_fetch (&References, 1U, __ATOMIC_ACQ_REL) == 0) delete this;
	}
	static void Cleanup (void *context)
	{
		auto *state = static_cast<TUSBSerialAsyncState *> (context);
		// A queued URB may be destroyed without completion on device removal.
		state->Release ();
	}
	static void Completion (CUSBRequest *urb, void *, void *context)
	{
		auto *state = static_cast<TUSBSerialAsyncState *> (context);
		state->Result = urb->GetStatus () ? (int) urb->GetResultLength () : -1;
		__atomic_store_n (&state->Complete, 1U, __ATOMIC_RELEASE);
		delete urb; // OwnerCleanup releases the request's reference exactly once.
	}
};

CUSBSerialHostDevice::CUSBSerialHostDevice (CUSBFunction *pFunction, size_t nReadHeaderBytes)
:	CUSBFunction (pFunction),
	m_nBaudRate (9600),
	m_nDataBits (USBSerialDataBits8),
	m_nParity (USBSerialParityNone),
	m_nStopBits (USBSerialStopBits1),
	m_pAsync (0),
	m_pInterface (0),
	m_nReadHeaderBytes (nReadHeaderBytes),
	m_pEndpointIn (0),
	m_pEndpointOut (0),
	m_pBufferIn (0),
	m_nBufferInSize (0),
	m_nBufferInValid (0),
	m_nBufferInPtr (0),
	m_bInRequestActive (FALSE)
{
}

CUSBSerialHostDevice::~CUSBSerialHostDevice (void)
{
	delete m_pInterface;
	m_pInterface = 0;

	if (m_pAsync != 0)
	{
		// USB device teardown has requested cancellation. Outstanding URBs own
		// their state/endpoints until the controller delivers completion.
		m_pEndpointIn = 0;
		m_pEndpointOut = 0;
		m_pAsync->Release ();
		m_pAsync = 0;
	}

	delete m_pEndpointOut;
	m_pEndpointOut =  0;
	
	delete m_pEndpointIn;
	m_pEndpointIn = 0;

	delete [] m_pBufferIn;
	m_pBufferIn = 0;
	m_nBufferInSize = 0;
}

boolean CUSBSerialHostDevice::Configure (void)
{
	const TUSBEndpointDescriptor *pEndpointDesc;
	while ((pEndpointDesc = (TUSBEndpointDescriptor *) GetDescriptor (DESCRIPTOR_ENDPOINT)) != 0)
	{
		if ((pEndpointDesc->bmAttributes & 0x3F) == 0x02)		// Bulk
		{
			if ((pEndpointDesc->bEndpointAddress & 0x80) == 0x80)	// Input
			{
				if (m_pEndpointIn != 0)
				{
					ConfigurationError (From);

					return FALSE;
				}

				m_pEndpointIn = new CUSBEndpoint (GetDevice (), pEndpointDesc);
			}
			else							// Output
			{
				if (m_pEndpointOut != 0)
				{
					ConfigurationError (From);

					return FALSE;
				}

				m_pEndpointOut = new CUSBEndpoint (GetDevice (), pEndpointDesc);
			}
		}
	}

	if (   m_pEndpointIn == 0
	    || m_pEndpointOut == 0)
	{
		ConfigurationError (From);

		return FALSE;
	}

	m_nBufferInSize = m_pEndpointIn->GetMaxPacketSize ();
	m_pBufferIn = new u8[m_nBufferInSize];
	assert (m_pBufferIn != 0);

	if (!CUSBFunction::Configure ())
	{
		LOGERR ("Cannot set interface");

		return FALSE;
	}

	// attach interface device
	assert (m_pInterface == 0);
	m_pInterface = new CUSBSerialDevice (this, this);
	assert (m_pInterface != 0);

	m_pInterface->RegisterWriteHandler (WriteHandler, this);
	m_pInterface->RegisterReadHandler (ReadHandler, this);
	m_pInterface->RegisterSetBaudRateHandler (SetBaudRateHandler, this);
	m_pInterface->RegisterSetLinePropertiesHandler (SetLinePropertiesHandler, this);

	return TRUE;
}

int CUSBSerialHostDevice::Write (const void *pBuffer, size_t nCount)
{
	assert (m_pAsync == 0);
	assert (pBuffer != 0);
	assert (nCount > 0);

#if RASPPI <= 3
	// USB host controller does not allow concurrent split transactions
	// to same device. Thus wait for completion of pending IN request.
	do
	{
		DataMemBarrier ();
	}
	while (m_bInRequestActive);
#endif

	CUSBHostController *pHost = GetHost ();
	assert (pHost != 0);

	DMA_BUFFER (u8, BufferOut, nCount);
	memcpy (BufferOut, pBuffer, nCount);

	assert (m_pEndpointOut != 0);
	int nActual = pHost->Transfer (m_pEndpointOut, BufferOut, nCount);
	if (nActual < 0)
	{
		LOGWARN ("USB write failed");
	}

	return nActual;
}

int CUSBSerialHostDevice::Read (void *pBuffer, size_t nCount)
{
	assert (m_pAsync == 0);
	assert (pBuffer != 0);
	assert (nCount > 0);

	DataMemBarrier ();

	if (m_bInRequestActive)
	{
		return 0;
	}

	assert (m_pBufferIn != 0);
	assert (m_nBufferInSize > 0);
	assert (m_nBufferInValid <= m_nBufferInSize);
	assert (m_nBufferInPtr <= m_nBufferInValid);

	if (m_nBufferInPtr == m_nBufferInValid)		// buffer empty?
	{
		CUSBHostController *pHost = GetHost ();
		assert (pHost != 0);

		assert (m_pEndpointIn != 0);
		CUSBRequest *pURB = new CUSBRequest (m_pEndpointIn, m_pBufferIn, m_nBufferInSize);
		assert (pURB != 0);

		// do not retry if request cannot be served immediately
		pURB->SetCompleteOnNAK ();

		pURB->SetCompletionRoutine (CompletionStub, 0, this);
		m_bInRequestActive = TRUE;

		if (!pHost->SubmitAsyncRequest (pURB))
		{
			LOGWARN ("USB read failed");

			m_bInRequestActive = FALSE;

			delete pURB;

			return -1;
		}

		return 0;
	}

	size_t nRemain = m_nBufferInValid - m_nBufferInPtr;
	if (nRemain < nCount)
	{
		nCount = nRemain;
	}

	assert (nCount > 0);
	memcpy (pBuffer, m_pBufferIn + m_nBufferInPtr, nCount);
	m_nBufferInPtr += nCount;

	return nCount;
}

boolean CUSBSerialHostDevice::SetBaudRate (unsigned nBaudRate)
{
	return TRUE;
}

boolean CUSBSerialHostDevice::SetLineProperties (TUSBSerialDataBits nDataBits,
						 TUSBSerialParity nParity,
						 TUSBSerialStopBits nStopBits)
{
	return TRUE;
}

void CUSBSerialHostDevice::CompletionRoutine (CUSBRequest *pURB)
{
	assert (pURB != 0);
	assert (m_bInRequestActive);
	assert (m_nBufferInValid == m_nBufferInPtr);

	if (pURB->GetStatus () != 0)
	{
		m_nBufferInValid = pURB->GetResultLength ();
		m_nBufferInPtr = m_nReadHeaderBytes;

		if (   m_nBufferInValid == 0
		    || m_nBufferInValid == m_nBufferInPtr)
		{
			m_nBufferInValid = 0;
			m_nBufferInPtr = 0;
		}
		else if (m_nBufferInValid < m_nBufferInPtr)
		{
			LOGWARN ("Missing read header");

			m_nBufferInValid = 0;
			m_nBufferInPtr = 0;
		}
	}

	delete pURB;

	m_bInRequestActive = FALSE;
	DataSyncBarrier ();
}

void CUSBSerialHostDevice::CompletionStub (CUSBRequest *pURB, void *pParam, void *pContext)
{
	CUSBSerialHostDevice *pThis = static_cast <CUSBSerialHostDevice *> (pContext);
	assert (pThis != 0);

	pThis->CompletionRoutine (pURB);
}

int CUSBSerialHostDevice::WriteHandler (const void *pBuffer, size_t nCount, void *pParam)
{
	CUSBSerialHostDevice *pThis = static_cast <CUSBSerialHostDevice *> (pParam);
	assert (pThis != 0);

	return pThis->Write (pBuffer, nCount);
}

int CUSBSerialHostDevice::ReadHandler (void *pBuffer, size_t nCount, void *pParam)
{
	CUSBSerialHostDevice *pThis = static_cast <CUSBSerialHostDevice *> (pParam);
	assert (pThis != 0);

	return pThis->Read (pBuffer, nCount);
}

boolean CUSBSerialHostDevice::SetBaudRateHandler (unsigned nBaudRate, void *pParam)
{
	CUSBSerialHostDevice *pThis = static_cast <CUSBSerialHostDevice *> (pParam);
	assert (pThis != 0);

	return pThis->SetBaudRate (nBaudRate);
}

boolean CUSBSerialHostDevice::SetLinePropertiesHandler (TUSBSerialDataBits nDataBits,
							TUSBSerialParity nParity,
							TUSBSerialStopBits nStopBits,
							void *pParam)
{
	CUSBSerialHostDevice *pThis = static_cast <CUSBSerialHostDevice *> (pParam);
	assert (pThis != 0);

	return pThis->SetLineProperties (nDataBits, nParity, nStopBits);
}

boolean CUSBSerialHostDevice::EnableAsyncIO (void)
{
#if RASPPI == 3
	if (m_pAsync) return TRUE;
	if (m_bInRequestActive || !m_pEndpointIn || !m_pEndpointOut
	    || m_pEndpointIn->GetMaxPacketSize () > 64
	    || m_pEndpointOut->GetMaxPacketSize () > 64) return FALSE;
	m_pAsync = new TUSBSerialAsyncState (m_pEndpointIn, m_pEndpointOut, m_nReadHeaderBytes);
	return m_pAsync != 0;
#else
	return FALSE; // Phase 2 targets the Pi 3 DWC controller only.
#endif
}

boolean CUSBSerialHostDevice::SerialPacketIdle (void) const
{
	return !m_pAsync || !m_pAsync->Pending;
}

int CUSBSerialHostDevice::SubmitSerialPacket (boolean in, const void *data, unsigned count)
{
	if (!m_pAsync) return -1;
	auto *state = m_pAsync;
	if (state->Pending) return 0;
	if (!count || count > 64 || (!in && !data)) return -1;
	if (in) count = state->PacketSize; // Exactly one FTDI header per packet.
	else
	{
		if (count > state->Out->GetMaxPacketSize ()) return -1;
		memcpy (state->Buffer, data, count);
	}
	state->Input = in;
	state->Pending = TRUE;
	__atomic_store_n (&state->Complete, 0U, __ATOMIC_RELAXED);
	auto *urb = new CUSBRequest (in ? state->In : state->Out, state->Buffer, count);
	if (in) urb->SetCompleteOnNAK ();
	urb->SetCompletionRoutine (TUSBSerialAsyncState::Completion, 0, state);
	urb->SetOwnerCleanup (TUSBSerialAsyncState::Cleanup, state);
	__atomic_add_fetch (&state->References, 1U, __ATOMIC_RELAXED);
	// DWHCI supports finite timeouts only for interrupt endpoints. Passing
	// 50 here asserts in CDWHCITransferStageData before the first bulk packet
	// reaches the controller. Async submission does not wait for completion;
	// IN completes on NAK, and removal retains/cancels the outstanding URB.
	if (!GetHost ()->SubmitAsyncRequest (urb))
	{
		delete urb;
		state->Pending = FALSE;
		return -1;
	}
	return 1;
}

int CUSBSerialHostDevice::PollSerialPacket (void *data, unsigned capacity)
{
	return PollSerialPacketWithStatus (data, capacity, 0);
}

int CUSBSerialHostDevice::PollSerialPacketWithStatus (void *data, unsigned capacity,
						    TUSBSerialPacketStatus *status)
{
	if (status) *status = {FALSE, 0, 0};
	if (!m_pAsync || !m_pAsync->Pending) return -1;
	auto *state = m_pAsync;
	if (!__atomic_load_n (&state->Complete, __ATOMIC_ACQUIRE)) return -2;
	state->Pending = FALSE;
	int result = state->Result;
	if (result < 0 || result > 64) return -1;
	if (!state->Input) return result;
	if (result == 0) return 0; // NAK: no data.
	if ((unsigned) result < state->Header) return -1;
	result -= state->Header;
	if ((unsigned) result > capacity || (result && !data)) return -1;
	if (status && state->Header == 2)
	{
		status->HeaderValid = TRUE;
		status->ModemStatus = state->Buffer[0];
		status->LineStatus = state->Buffer[1];
	}
	if (result) memcpy (data, state->Buffer + state->Header, result);
	return result;
}
