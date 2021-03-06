// (C) 2017 Landon Meernik. Beerware License.
#include <stdint.h>
#include <stdio.h>
#include <pru_cfg.h>
#include <pru_ctrl.h>
#include <pru_intc.h>
#include <rsc_types.h>
#include <pru_rpmsg.h>
#include "resource_table.h"
// This is a program already in progress, start reading at ./resource_table.h
// This part runs on the PRU coprocessor, and does actual WS2812 signal generation.

volatile register uint32_t __R31; // magic interrupt control and other shit register
volatile register uint32_t __R30; // Output register


uint8_t payload[RPMSG_BUF_SIZE];

void 
display_2812B(void* buffer, uint16_t nregs)
{
/* 
This assumes data has been munged up into register-at-a-time format by opcd.c
See also: https://wp.josh.com/2014/05/13/ws2812-neopixels-are-not-so-finicky-once-you-get-to-know-them/
   Reshaped timing:
   T0H = 400ns
   T0L = 1000ns
   T1H = 600ns
   T1L = 800ns
*/
	uint32_t data;
	CTRL_REG.CYCLE = 0;
	__R30 = 0x0;
	data = ((uint16_t*)buffer)[0];
	while(CTRL_REG.CYCLE < 20000); // reset
	uint16_t i;
	for (i = 1; i <= nregs; i++) { 
		CTRL_REG.CYCLE = 0;
		__R30 = 0xFFFF; 
		while(CTRL_REG.CYCLE < 60); // ~T0H 
		__R30 = data;
		while(CTRL_REG.CYCLE < 200); // ~T1H
		__R30 = 0x0000;
		data = ((uint16_t*)buffer)[i]; // Who knows how many cycles, that's why it's at the end
		while(CTRL_REG.CYCLE < 280); // ~TnH + TnL
	}
}

struct memmsg {
	uint32_t pa;
	uint32_t len;
};

void main(void)
{
	CT_CFG.GPCFG0 = 0;
	volatile uint8_t *status;
	uint16_t src, dst, len;
	struct pru_rpmsg_transport transport;

	CT_CFG.SYSCFG_bit.STANDBY_INIT = 0;
	CT_INTC.SICR_bit.STS_CLR_IDX = FROM_ARM_HOST;

	status = &resourceTable.rpmsg_vdev.status;
	while (!(*status & VIRTIO_CONFIG_S_DRIVER_OK)); // Wait for linux
	CTRL_REG.CTRL_bit.CTR_EN = 1;

	// Initialize vrings
	pru_rpmsg_init(&transport, &resourceTable.rpmsg_vring0, &resourceTable.rpmsg_vring1, (16 + (PRU_NO * 2)), FROM_ARM_HOST);

	// I guess the thing above wasn't enough shit initialization, so do more.
	// "rpmsg-pru" here is magic, it tells the kernel which driver to use on the host side
	while (pru_rpmsg_channel(RPMSG_NS_CREATE, &transport, "rpmsg-pru", "Stay out", (30 + PRU_NO)) != PRU_RPMSG_SUCCESS);
	while (1) { 
		// Do we have a message?
		if (__R31 & ((uint32_t) 1 << (PRU_NO + 30))) {
			// Let the host know it can interrupt us again
			CT_INTC.SICR_bit.STS_CLR_IDX = FROM_ARM_HOST;
			// this is like recv() but fancier.
			while (pru_rpmsg_receive(&transport, &src, &dst, payload, &len) == PRU_RPMSG_SUCCESS) {
				if (payload[0] == 'a') { // address of carveout
					struct memmsg msg;
					msg.pa = resourceTable.fb.pa;
					msg.len = resourceTable.fb.len;
					pru_rpmsg_send(&transport, dst, src, &msg, sizeof(msg));
				} else if (payload[0] == 'd') { // display
					uint16_t nregs = ((uint16_t*)(payload+1))[0];
					display_2812B((uint16_t*)resourceTable.fb.pa, nregs);
					pru_rpmsg_send(&transport, dst, src, &nregs, sizeof(nregs));
				} else if (payload[0] == 'p') { // ping
					pru_rpmsg_send(&transport, dst, src, "p", 1);
				} else if (payload[0] == 'P') {
					while(1) {
						uint32_t i;
						for (i = 0; i < 100000; i++);
						pru_rpmsg_send(&transport, dst, src, "p", 1);
					}
				}
			}
		}
	}
}
