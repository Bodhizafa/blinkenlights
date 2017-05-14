// (C) 2017 Landon Meernik. Beerware License.
#include <stdint.h>
#include <stdio.h>
#include <pru_cfg.h>
#include <pru_intc.h>
#include <rsc_types.h>
#include <pru_rpmsg.h>
#include "resource_table.h"

volatile register uint32_t __R31;

// More magic numbers. Woooo
#define FROM_ARM_HOST			(17 + (PRU_NO * 2))

// More magic numbers. Woooo
#define VIRTIO_CONFIG_S_DRIVER_OK	4

uint8_t payload[RPMSG_BUF_SIZE];

void main(void)
{
	volatile uint8_t *status;
	uint16_t src, dst, len;
	struct pru_rpmsg_transport transport;

	/* Allow OCP master port access by the PRU so the PRU can read external memories */
	CT_CFG.SYSCFG_bit.STANDBY_INIT = 0;

	/* Clear the status of the PRU-ICSS system event that the ARM will use to 'kick' us */
	CT_INTC.SICR_bit.STS_CLR_IDX = FROM_ARM_HOST;

	/* Make sure the Linux drivers are ready for RPMsg communication */
	status = &resourceTable.rpmsg_vdev.status;
	while (!(*status & VIRTIO_CONFIG_S_DRIVER_OK));

	/* Initialize the RPMsg transport structure */
	pru_rpmsg_init(&transport, &resourceTable.rpmsg_vring0, &resourceTable.rpmsg_vring1, (16 + (PRU_NO * 2)), FROM_ARM_HOST);

	// 'rpmsg-pru' here is magic, it tells the kernel which driver to use on the host side
	while (pru_rpmsg_channel(RPMSG_NS_CREATE, &transport, "rpmsg-pru", "Stay out", (30 + PRU_NO)) != PRU_RPMSG_SUCCESS);
	while (1) {
		/* Check bit 30 of register R31 to see if the ARM has kicked us */
		if (__R31 & ((uint32_t) 1 << (PRU_NO + 30))) {
			/* Clear the event status */
			CT_INTC.SICR_bit.STS_CLR_IDX = FROM_ARM_HOST;
			/* Receive all available messages, multiple messages can be sent per kick */
			while (pru_rpmsg_receive(&transport, &src, &dst, payload, &len) == PRU_RPMSG_SUCCESS) {
				/* Echo the message back to the same address from which we just received */
				pru_rpmsg_send(&transport, dst, src, payload, len);
			}
		}
	}
}
