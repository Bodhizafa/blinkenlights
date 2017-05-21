// (C) 2017 Landon Meernik. Beerware license.
// Based on /usr/lib/ti/pru-software-support-package/examples/am335x/PRU_RPMsg_Echo_Interrupt*
// This file (along with pru_main.c) gets build twice, once with PRU_NO=0 and once with PRU_NO=1
// and the results are loaded on their respective PRU

// Currently located at /usr/lib/ti/pru-software-support-package/examples/am335x/*
// but they tend to teleport around at random when releases happen.

#ifndef _RSC_TABLE_PRU_H_
#define _RSC_TABLE_PRU_H_

#include <stddef.h>
#include <rsc_types.h>
#include "pru_virtio_ids.h"

// First we define some bullshit, you don't care about this.

// Size of vqueues (must be power of 2)
#define PRU_RPMSG_VQ0_SIZE	16
#define PRU_RPMSG_VQ1_SIZE	16
// Size of framebuffers
// make them large, the host doesn't give a fuck about 64k, 
// and it's _way_ more lights than we currently care about.
#define FRAMEBUFFER_SIZE 	(1<<16)

// The bit that gets set when we're supposed to service a message (in register 31)
#define FROM_ARM_HOST			(17 + (PRU_NO * 2))

// The PRUs ahve different control registers, which are used to enable the cycle counters later.
#if PRU_NO == 0
#define CTRL_REG			PRU0_CTRL
#elif PRU_NO == 1
#define CTRL_REG			PRU1_CTRL

#endif
// MAGIC
#define VIRTIO_RPMSG_F_NS	0
#define VIRTIO_CONFIG_S_DRIVER_OK	4

// MORE MAGIC
#define RPMSG_PRU_C0_FEATURES	(1 << VIRTIO_RPMSG_F_NS)

// YET MORE MAGIC
struct ch_map pru_intc_map[] = { {(16 + (2 * PRU_NO)), (2 + PRU_NO)},
				 {(17 + (2 * PRU_NO)), (0 + PRU_NO)},
};

// It's shit like this, C. So in this file, 3 things need to be kept in sync. 
// To add things, all 5 must be modified accordingly
// In the beginning, there were 2, the intc, and the rpmsg_vdev.
// We're adding 2 framebuffers (one to write to, one to read from)

// See also: https://www.kernel.org/doc/Documentation/remoteproc.txt
// See also: http://elixir.free-electrons.com/linux/v(YOUR VERSION HERE)/source/include/linux/remoteproc.h 
struct my_resource_table {
	struct resource_table base;

	// 1st thing - Increment number of entries here
	uint32_t offset[4];  
	// 2nd thing: Add a struct here. Offsets, so some thing take more than one struct.

	// First offset  - framebuffer 0
	struct fw_rsc_carveout fb0;
	// Second offset - framebuffer 1
	struct fw_rsc_carveout fb1;
	// Third offset  - rpmsg thing (and its two vrings. 
	struct fw_rsc_vdev rpmsg_vdev;
	// This is why offsets are used, cause some entries are wide)
	struct fw_rsc_vdev_vring rpmsg_vring0;
	struct fw_rsc_vdev_vring rpmsg_vring1;

	// Fourth offset - interrupt controller
	struct fw_rsc_custom pru_ints;
};

#pragma DATA_SECTION(resourceTable, ".resource_table")
#pragma RETAIN(resourceTable)
// Alright, so so far we've got 2 things in sync, and we've defined the structure we're about to use. 
// This is sent by the firmware to the kernel, and the kernel fills various values in it out, which
// are available to the PRU program (and presumably also the kernel, but I haven't got there yet)

struct my_resource_table resourceTable = {
	1,	// Version, must be 1
	4,	// 3rd thing, the number of offsets _here_ too.
	0, 0,	// reserved, be 0
	// 4th thing:  into the struct
	{
		offsetof(struct my_resource_table, fb0),
		offsetof(struct my_resource_table, fb1),
		offsetof(struct my_resource_table, rpmsg_vdev),
		offsetof(struct my_resource_table, pru_ints),
	},
	// 5th thing: Actual entries in the struct, defined in the kernel (linked above)
	{
		(uint32_t)TYPE_CARVEOUT,
		(uint32_t)(0xFFFFFFFFFFFFFFFF), // I think this means "kernel assign me an address" 
		(uint32_t)(0xFFFFFFFFFFFFFFFF),
		(uint32_t)FRAMEBUFFER_SIZE,
		(uint32_t)0,
		(uint32_t)0,
		"Framebuffer 0"
	},
	{
		(uint32_t)TYPE_CARVEOUT,
		(uint32_t)(0xFFFFFFFFFFFFFFFF),
		(uint32_t)(0xFFFFFFFFFFFFFFFF),
		(uint32_t)FRAMEBUFFER_SIZE,
		(uint32_t)0,
		(uint32_t)0,
		"Framebuffer 1"
	},
	{
		(uint32_t)TYPE_VDEV,
		(uint32_t)VIRTIO_ID_RPMSG,
		(uint32_t)0,
		(uint32_t)RPMSG_PRU_C0_FEATURES,
		(uint32_t)0,
		(uint32_t)0,
		(uint8_t)0,
		(uint8_t)2,
		{ (uint8_t)0, (uint8_t)0 },
	},
	{
		0,                      //da, will be populated by host, can't pass it in
		16,                     //align (bytes),
		PRU_RPMSG_VQ0_SIZE,     //num of descriptors
		0,                      //notifyid, will be populated, can't pass right now
		0                       //reserved
	},
	{
		0,                      //da, will be populated by host, can't pass it in
		16,                     //align (bytes),
		PRU_RPMSG_VQ1_SIZE,     //num of descriptors
		0,                      //notifyid, will be populated, can't pass right now
		0                       //reserved
	},

	{
		TYPE_CUSTOM, TYPE_PRU_INTS,
		// MAGIC
		sizeof(struct fw_rsc_custom_ints),
		{ 
			0x0000,
			// Channel map, appear to be 10 channels, 0xFF means unused
			// These also appear to be global, cause each PRU's is different.
#if PRU_NO==0
			0x00, 0xFF, 0x02, 0xFF, 0xFF,
#else
			0xFF, 0x01, 0xFF, 0x03, 0xFF,
#endif
			0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
			(sizeof(pru_intc_map) / sizeof(struct ch_map)),
			pru_intc_map,
		},
	},
};

#endif /* _RSC_TABLE_PRU_H_ */
