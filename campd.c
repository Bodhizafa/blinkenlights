#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>

#define NUM_PRUS 2

typedef struct __attribute__((__packed__)) {
	int msg_fd;
	uint32_t fb; // 32 bit pointer
	uint32_t fblen;
} pru;

static pru prus[NUM_PRUS];

bool write_str(int fd, char* str) {
	size_t len = strlen(str);
	while (len > 0) {
		ssize_t written = write(fd, str, len);
		if (written < 0) {
			return false;
		}
		str += written;
		len -= written;
	}
	return true;
}

bool read_buf(int fd, void* buf, size_t len) {
	while (len > 0) {
		int nread = read(fd, buf, len);
		if (nread < 0) {
			return false;
		}
		len -= nread;
	}
	return true;
}

bool init() {
	// Reboot the  PRUs
	int unbind_fd = open("/sys/bus/platform/drivers/pru-rproc/unbind", O_WRONLY);
	if (unbind_fd <= 0) {
		perror("Opening unbind");
		return false;
	}
	int bind_fd = open("/sys/bus/platform/drivers/pru-rproc/unbind", O_WRONLY);
	if (bind_fd <= 0) {
		perror("Opening bind");
		return false;
	}
	printf("Opened bind/unbind FDs\n");
	if (!write_str(unbind_fd, "4a334000.pru0")) {
		perror("Failed to unbind PRU0");
	}
	if (!write_str(unbind_fd, "4a338000.pru1")) {
		perror("Failed to unbind PRU1");
	}
	printf("Stopped PRUs\n");
	if (!write_str(bind_fd, "4a334000.pru0\n")) {
		perror("Failed to bind PRU0");
		return false;
	}
	if (!write_str(bind_fd, "4a338000.pru1\n")) {
		perror("Failed to bind PRU1");
		return false;
	}
	printf("Started PRUs\n");
	// Open the PRU MSG FDs
	prus[0].msg_fd = open("/dev/rpmsg_pru30", O_RDWR);
	if (prus[0].msg_fd < 0) {
		perror("Opening PRU0");
		return false;
	}
	prus[1].msg_fd = open("/dev/rpmsg_pru31", O_RDWR);
	if (prus[1].msg_fd < 0) {
		perror("Opening PRU1");
		return false;
	}
	printf("Opened MSG FDs\n");
	// Get the FB addresses
	for (int i = 0; i < NUM_PRUS; i++) {
		write_str(prus[i].msg_fd, "a");
		if (!read_buf(prus[i].msg_fd, &(prus[i].fb), sizeof(uint32_t) * 2)) {
			printf("PRU %d ", i);
			perror("Reading address");
			return false;
		}
	}
	// In theory we're done
	return true;
}

int main(int argc, char** argv) {
	printf("Starting\n");
	if (!init()) {
		printf("Failed to start PRUs. Reinstall firmware?\n");
		return 1;
	}
	printf("PRUs initialized");
	for (int i = 0; i < NUM_PRUS; i++) {
		printf("PRU %d FD %d Address %p\n", i, prus[i].msg_fd, prus[i].fb);
	}
}
