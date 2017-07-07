#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <uv.h>

#define NUM_PRUS 2

typedef struct pru {
	int msg_fd;
	uint16_t* fb;
	uint32_t fblen;
} pru_t;

typedef struct __attribute__((__packed__)) addr_msg {
	uint32_t pa;
	uint32_t len;
} addr_msg_t;

static pru_t prus[NUM_PRUS];

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
		ssize_t nread = read(fd, buf, len);
		if (nread < 0) {
			return false;
		} else if (nread > len) { // Yeah, this actually happens. Thanks, TI.
			printf("Read too much shit\n"); 
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
	int bind_fd = open("/sys/bus/platform/drivers/pru-rproc/bind", O_WRONLY);
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
	close(unbind_fd);
	if (!write_str(bind_fd, "4a334000.pru0\n")) {
		perror("Failed to bind PRU0");
		return false;
	}
	if (!write_str(bind_fd, "4a338000.pru1\n")) {
		perror("Failed to bind PRU1");
		return false;
	}
	printf("Started PRUs\n");
	close(bind_fd);
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
	// If we were classy, we'd write a kernel driver and get the carveouts from there
	// But we're not, and beaglebones come with the kernel flag that lets you write 
	// 	directly to physical memory, so we do that instead, getting the FB addresses
	// 	out of band via the message interface.
	int devmem_fd = open("/dev/mem", O_RDWR);
	if (devmem_fd < 0) {
		perror("Opening /dev/mem");
		return false;
	}
	// Get the framebuffer
	for (int i = 0; i < NUM_PRUS; i++) {
		write_str(prus[i].msg_fd, "a");
		// Read framebuffer info from the PRU
		addr_msg_t msg = {0, 0};
		if (!read_buf(prus[i].msg_fd, &msg, sizeof(msg))) {
			printf("PRU %d ", i);
			perror("Reading FB info");
			return false;
		}
		prus[i].fblen = msg.len;
		// Map the memory
		prus[i].fb = mmap(NULL, prus[i].fblen, PROT_READ | PROT_WRITE, 
		                  MAP_SHARED | MAP_LOCKED, devmem_fd, msg.pa);
		if (prus[i].fb == MAP_FAILED) {
			printf("PRU %d ", i);
			perror("mmap failed");
			return false;
		}
		printf("PRU %d FD %d Address 0x%x => %p len 0x%x\n", 
		       i, prus[i].msg_fd, msg.pa, prus[i].fb, prus[i].fblen);
		
	}
	// In theory we're done
	return true;
}
// LibUV allows custom memory allocators. We don't care, but we need to provide an allocator
// So we use a shim around malloc
void opc_malloc(uv_handle_t *handle, size_t suggested_size, uv_buf_t *buf) {
    buf->base = (char*)malloc(suggested_size);
    buf->len = suggested_size;
}

struct __attribute__((__packed__)) opc_pkt {
	uint32_t pkt_len;
	uint16_t channel;
	uint16_t command;
	char body[];
};

struct opc_uv_data {
	uv_mutex_t lock;
	enum {
		COMPLETED, 	// pkt is unallocated (and should be NULL)
		PARTIAL_LEN,	// pkt is a 4 byte allocation, size has not yet been recieved
		COMPLETED_LEN,	// pkt is a 4 byte allocation, size has been recieved
		ALLOCATED	// pkt is fully allocated
		
	} pkt_state;
	size_t pkt_sofar; // Bytes so far (i.e. current offset into buf). 0 if last packet was completed
	union {
		struct opc_pkt* pkt; // Pointer to packet buffer. NULL if last packet was completed
		char* pkt_ptr;
	};
};

// CAMP is stateless and pragmatically a bit dumpster, so we don't get a client reference
void opc_dispatch(struct opc_pkt* p) { 
	fprintf(stderr, "Complete packet recieved");
};

// libuv Event Handlers
void on_close(uv_handle_t *handle) {
	free(handle);
}

void on_packet(uv_stream_t* client, struct opc_pkt* pkt) {
	printf("Recieved packet"); //TODO this
}

void on_recv(uv_stream_t* client, ssize_t nread, const uv_buf_t* uv_buf) {
	if (nread > 0) {
		printf("Got a packet \n%.*s\n", uv_buf->len);
		struct opc_uv_data* uv_data = (struct opc_uv_data*)client->data;
		uv_mutex_lock(&(uv_data->lock));
		char* buf = uv_buf->base;
		while (nread > 0) {
			switch (uv_data.pkt_state) {
				case COMPLETED:
					uv_data.pkt = malloc(sizeof(uv_data.pkt->pkt_len))
					if (nread < sizeof(uv_data.pkt->pkt_len)) {
						uv_data.pkt_state = PARTIAL_LEN;
						memcpy(uv_data.pkt, buf, nread);
						uv_data.pkt_sofar = nread;
						nread = 0;
						break;
						// done
					} else {
						// In this case we malloc and immediately realloc, which isn't great.
						uv_data.pkt_state = COMPLETED_LEN;
						memcpy(uv_data.pkt, buf->base, sizeof(uv_data.pkt->pkt_len));
						uv_data.pkt_sofar = sizeof(uv_data.pkt->pkt_len);
						buf += sizeof(uv_data.pkt->pkt_len);
						nread -= sizeof(uv_data.pkt->pkt_len);
						goto completed_len;
					}
				case PARTIAL_LEN:
					if (nread + uv_data.pkt_sofar < sizeof(uv_data.pkt->pkt_len)) {
						// length is still partial
						memcpy(uv_data.pkt_ptr + uv_data.pkt_sofar, buf, nread);
						uv_data.pkt_sofar += nread;
						nread = 0;
						break;
						// done
					} else {
						// We got the whole length, and we had part of it before. 
						uv_data.pkt_state = COMPLETED_LEN;
						size_t to_copy = sizeof(uv_data.pkt->pkt_len) - uv_data.pkt_sofar;
						memcpy(uv_data.pkt_ptr + uv_data.pkt_sofar, buf, to_copy);
						uv_data.pkt_sofar = sizeof(uv_data.pkt->pkt_len);
						buf += to_copy;
						nread -= to_copy;
						// fallthrough
					}
				completed_len:
				case COMPLETED_LEN:
					uv_data.pkt = realloc(uv_data.pkt, uv_data.pkt->pkt_len)
					uv_data.pkt_state = ALLOCATED;
					// fallthrough
				case ALLOCATED:
					if (nread  + uv_data.pkt_sofar >= uv_data.pkt->pkt_size) { // we got the end of the packet
						uv_data.pkt_state = COMPLETED;
						to_copy = uv_data.pkt_sofar - uv_data.pkt.pkt_size;
					} else {
						to_copy = nread;
						uv_data.pkt_sofar += nread;
					}
					memcpy(uv_data.pkt_ptr + uv_data.pkt_sofar, buf, to_copy);
					uv_data.pkt_sofar += to_copy;
			}
		}
		//  TODO The shit that was here was wrong
		uv_mutex_unlock(&(uv_data.lock));
	} else if (nread < 0) {
		if (nread != UV_EOF) {
			fprintf(stderr, "Read error %s\n", uv_strerror(nread));
		} else {
			fprintf(stdout, "Client disconnected %s\n", uv_strerror(nread));
		}
		uv_close((uv_handle_t*)client, on_close);
	}
	free(buf->base);
}

void on_connect(uv_stream_t* server, int status) {
	if (status < 0) {
		fprintf(stderr, "New connection error %s\n", uv_strerror(status));
		return;
	} else {
		fprintf(stdout, "New Client connection");
	}
	uv_tcp_t *client = malloc(sizeof(uv_tcp_t));
	if (client == NULL) {
		fprintf(stderr, "Could not allocate client");
		return;
	}
	uv_tcp_init(server->loop, client);
	sturct opc_data uv_data = calloc(1, sizeof(uv_data));
	if (uv_data == NULL) {
		fprintf(stderr, "Allocating client data failed");
		free(client);
		return;
	}
	uv_mutex_init(&(uv_data.lock));
	client->data  = calloc(sizeof(*(client->data)));
	if (uv_accept(server, (uv_stream_t*)client) == 0) {
		uv_read_start((uv_stream_t*)client, opc_malloc, on_recv);
	} else {
		fprintf(stderr, "uv_accept failed");
		uv_close((uv_handle_t*)client, on_close);
	}
}

uv_loop_t* loop;
int main(int argc, char** argv) {
	printf("Starting\n");
	if (!init()) {
		printf("Failed to start PRUs. Reinstall firmware?\n");
		return 1;
	}
	printf("PRUs initialized\n");
	loop = uv_default_loop();
	uv_tcp_t server;
	uv_tcp_init(loop, &server);
	struct sockaddr_in addr_ip4;
	uv_ip4_addr("0.0.0.0", 420, &addr_ip4);
	// TODO IP6 support
	uv_tcp_bind(&server, (const struct sockaddr*)&addr_ip4, 0);
	int r = uv_listen((uv_stream_t*)&server, 128, on_connect);
	if (r) {
		fprintf(stderr, "Listen error %s\n", uv_strerror(r));
		return 2;
	}
	printf("Starting UV loop\n");
	r = (uv_run(loop, UV_RUN_DEFAULT));
	if (r != 0) {
		printf("UV Exited abnormally %d\n", r);
		return 3;
	}
	printf("UV Loop Exited\n");
	uv_loop_close(loop);
	return 0;
}
