//
// usbserialhost.h
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
#ifndef _circle_usb_usbserialhost_h
#define _circle_usb_usbserialhost_h

#include <circle/usb/usbfunction.h>
#include <circle/usb/usbendpoint.h>
#include <circle/usb/usbserial.h>
#include <circle/types.h>

struct TUSBSerialAsyncState;

// Raw two-byte receive header; interpretation belongs to the device's caller.
struct TUSBSerialPacketStatus
{
	boolean HeaderValid;
	u8 ModemStatus;
	u8 LineStatus;
};

class CUSBSerialHostDevice : public CUSBFunction /// Generic host driver for USB serial devices
{
public:
	CUSBSerialHostDevice (CUSBFunction *pFunction,
			      size_t nReadHeaderBytes = 0);	// number of bytes to be ignored
	virtual ~CUSBSerialHostDevice (void);

	boolean Configure (void);

	int Write (const void *pBuffer, size_t nCount);
	int Read (void *pBuffer, size_t nCount);

	// Opt-in Pi 3 single-packet API. Never mixes with legacy Read/Write.
	// All calls except completion run on the USB PnP owner core/task.
	boolean EnableAsyncIO (void);
	// 1 submitted, 0 busy, -1 invalid/submission failed. One IN OR OUT at a time.
	int SubmitSerialPacket (boolean bIn, const void *pData, unsigned nCount);
	// -2 pending, -1 failure, >=0 completed bytes; consumes completion once.
	int PollSerialPacket (void *pData, unsigned nCapacity);
	// Same completion/result contract. Status is reset on every call, including
	// pending, NAK, OUT and failure. Valid only for a complete two-byte header.
	int PollSerialPacketWithStatus (void *pData, unsigned nCapacity,
					 TUSBSerialPacketStatus *pStatus);
	boolean SerialPacketIdle (void) const;


	virtual boolean SetBaudRate (unsigned nBaudRate);
	virtual boolean SetLineProperties (TUSBSerialDataBits nDataBits,
					   TUSBSerialParity nParity,
					   TUSBSerialStopBits nStopBits);

private:
	void CompletionRoutine (CUSBRequest *pURB);
	static void CompletionStub (CUSBRequest *pURB, void *pParam, void *pContext);

	static int WriteHandler (const void *pBuffer, size_t nCount, void *pParam);
	static int ReadHandler (void *pBuffer, size_t nCount, void *pParam);
	static boolean SetBaudRateHandler (unsigned nBaudRate, void *pParam);
	static boolean SetLinePropertiesHandler (TUSBSerialDataBits nDataBits,
						 TUSBSerialParity nParity,
						 TUSBSerialStopBits nStopBits,
						 void *pParam);

protected:
	unsigned m_nBaudRate;
	TUSBSerialDataBits m_nDataBits;
	TUSBSerialParity m_nParity;
	TUSBSerialStopBits m_nStopBits;

private:
	TUSBSerialAsyncState *m_pAsync;
	CUSBSerialDevice *m_pInterface;

	size_t m_nReadHeaderBytes;

	CUSBEndpoint *m_pEndpointIn;
	CUSBEndpoint *m_pEndpointOut;

	u8 *m_pBufferIn;
	size_t m_nBufferInSize;
	size_t m_nBufferInValid;
	unsigned m_nBufferInPtr;

	volatile boolean m_bInRequestActive;
};

#endif
