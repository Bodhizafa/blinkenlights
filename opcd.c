/*
   Sleketon appropriated from: https://raw.githubusercontent.com/trevnorris/libuv-examples/master/tcp-echo.c
   Everything else by Landon Meernik
 */
#include <stdlib.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <assert.h>
#include <string.h>

#include "uv.h"
#define OPC_PIXEL_DATA 0
#define OPC_TEST 254
#define OPC_SYSEX 255

#define STRAND_LEN 300
#define PORT 42024
#define NUM_PRUS 2

struct __attribute__((__packed__)) color {
    uint8_t r;
    uint8_t g;
    uint8_t b;
};

typedef struct pru {
	int msg_fd;
	uint16_t* fb;
	uint32_t fblen;
    struct color *rgb_fb[16];
} pru_t;

typedef struct __attribute__((__packed__)) addr_msg {
	uint32_t pa;
	uint32_t len;
} addr_msg_t;

static pru_t prus[NUM_PRUS];
static uv_mutex_t pru_lock;
static uv_thread_t display_thread;


bool write_buf(int fd, char* buf, size_t len) {
	while (len > 0) {
		ssize_t written = write(fd, buf, len);
		if (written < 0) {
			return false;
		}
		buf += written;
		len -= written;
	}
	return true;
}

bool write_str(int fd, char* str) {
	size_t len = strlen(str);
    return write_buf(fd, str, len);
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

// This transforms bits from RGB strings in memory to the register-at-a-time format
// pru_main.c expects. The dst should be (16 * nlights * 3) bytes, each strand in src 
// should nlights * 3 bytes
uint16_t translate_colors(uint16_t* dst_regs, struct color* src_rgbs[16], size_t nlights) {
    uint16_t nregs = 0;
    for (size_t led = 0; led < nlights; led++) {
        for (int8_t bit = 7; bit >= 0; bit--) {
            uint16_t reg = 0;
            for (uint8_t ch = 0; ch < 16; ch++) {
                // extract the bit'th bit of the source
                uint8_t b = src_rgbs[ch][led].g & (1 << bit) ? 1 : 0; 
                // and shift it into reg in it's channel's pos
                reg |= b << ch;
            }
            //printf("led %d bit %hhd %hx\n", led, bit, reg);
            dst_regs[nregs] = reg;
            nregs += 1;
        }
        for (int8_t bit = 7; bit >= 0; bit--) {
            uint16_t reg = 0;
            for (uint8_t ch = 0; ch < 16; ch++) {
                // extract the bit'th bit of the source
                uint8_t b = src_rgbs[ch][led].r & (1 << bit) ? 1 : 0; 
                // and shift it into reg in it's channel's pos
                reg |= b << ch;
            }
            //printf("led %d bit %hhd %hx\n", led, bit, reg);
            dst_regs[nregs] = reg;
            nregs += 1;
        }
        for (int8_t bit = 7; bit >= 0; bit--) {
            uint16_t reg = 0;
            for (uint8_t ch = 0; ch < 16; ch++) {
                // extract the bit'th bit of the source
                uint8_t b = src_rgbs[ch][led].b & (1 << bit) ? 1 : 0; 
                // and shift it into reg in it's channel's pos
                reg |= b << ch;
            }
            //printf("led %d bit %hhd %hx\n", led, bit, reg);
            dst_regs[nregs] = reg;
            nregs += 1;
        }
        // TODO copy and paste the above for B and G
    }
    return nregs;
}

void display_thread_main(void* arg) {
    printf("Starting display thread\n");
    while (true) {
        uv_mutex_lock(&pru_lock);
        char buf[3]; // byte 0 is 'd', the other 2 are the number of regs
        buf[0] = 'd'; // display message
        uint16_t nregs = translate_colors(prus[0].fb, prus[0].rgb_fb, STRAND_LEN);
        memcpy(buf + 1, &nregs, sizeof(nregs));
        write_buf(prus[0].msg_fd, buf, 3);
        //write_buf(prus[0].msg_fd, "d\0\0", 3);
        uint16_t nregs_displayed;
        read_buf(prus[0].msg_fd, &nregs_displayed, 2);
        uv_mutex_unlock(&pru_lock);
        //usleep(1000 * 10); 
        //printf("translated %hu regs, displayed %hu\n", nregs, nregs_displayed);
    }
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
			              MAP_SHARED | MAP_LOCKED	, devmem_fd, msg.pa); 
		if (prus[i].fb == MAP_FAILED) {
			printf("PRU %d ", i);
			perror("mmap failed");
			return false;
		}
        *prus[i].fb = 9;
		printf("PRU %d FD %d Address 0x%x => %p len 0x%x\n", 
				i, prus[i].msg_fd, msg.pa, prus[i].fb, prus[i].fblen);

        // Allocate the RGB framebuffer
        for (int j = 0; j < 16; j++) {
            prus[i].rgb_fb[j] = calloc(STRAND_LEN, 3);
        }
	}
    uv_mutex_init(&pru_lock);
    
	// In theory we're done
	return true;
}

typedef struct {
	uv_write_t req;
	uv_buf_t buf;
} write_req_t;

static uint64_t data_cntr = 0;


static void on_close(uv_handle_t* handle) {
	free(handle);
}


static void after_write(uv_write_t* req, int status) {
	write_req_t* wr = (write_req_t*)req;

	if (wr->buf.base != NULL)
		free(wr->buf.base);
	free(wr);

	if (status == 0)
		return;

	fprintf(stderr, "uv_write error: %s\n", uv_strerror(status));

	if (status == UV_ECANCELED)
		return;

	assert(status == UV_EPIPE);
	uv_close((uv_handle_t*)req->handle, on_close);
}


static void after_shutdown(uv_shutdown_t* req, int status) {
	/*assert(status == 0);*/
	if (status < 0)
		fprintf(stderr, "err: %s\n", uv_strerror(status));
	fprintf(stderr, "data received: %lu\n", data_cntr / 1024 / 1024);
	data_cntr = 0;
	uv_close((uv_handle_t*)req->handle, on_close);
	free(req);
}

struct __attribute__((__packed__)) opc_pkt {
	struct __attribute((__packed__)) {
		uint8_t channel;
		uint8_t command;
		uint16_t body_len;
	} hdr;
	char body[];
};

struct opc_uv_data {
	uv_mutex_t lock;
	enum {
        INIT,
		COMPLETED, 	// pkt is unallocated (and should be NULL)
		PARTIAL_HDR,	// pkt is a 4 byte allocation, size has not yet been recieved
		COMPLETED_HDR,	// pkt is a 4 byte allocation, size has been recieved
		ALLOCATED	// pkt is fully allocated

	} pkt_state;
	size_t pkt_sofar; // Bytes so far (i.e. current offset into buf). 0 if last packet was completed
	union {
		struct opc_pkt* pkt; // Pointer to packet buffer. NULL if last packet was completed
		char* pkt_ptr;
	};
};

void print_regbuf(uint16_t* regs, uint16_t nregs) {
    printf("Dumping %hu regs", nregs);
    for (int i = 0; i < nregs; i++) {
        printf("%hu %c %c %c %c %c %c %c %c %c %c %c %c %c %c %c %c\n", nregs,
            regs[i] & (1 << 15) ? '1' : '0',
            regs[i] & (1 << 14) ? '1' : '0',
            regs[i] & (1 << 13) ? '1' : '0',
            regs[i] & (1 << 12) ? '1' : '0',
            regs[i] & (1 << 11) ? '1' : '0',
            regs[i] & (1 << 10) ? '1' : '0',
            regs[i] & (1 << 9) ? '1' : '0',
            regs[i] & (1 << 8) ? '1' : '0',
            regs[i] & (1 << 7) ? '1' : '0',
            regs[i] & (1 << 6) ? '1' : '0',
            regs[i] & (1 << 5) ? '1' : '0',
            regs[i] & (1 << 4) ? '1' : '0',
            regs[i] & (1 << 3) ? '1' : '0',
            regs[i] & (1 << 2) ? '1' : '0',
            regs[i] & (1 << 1) ? '1' : '0',
            regs[i] & (1 << 0) ? '1' : '0');
    }
}
// OPC is stateless and pragmatically a bit dumpster, so we don't get a client reference
void after_opc_packet(struct opc_pkt* p) { 
	//fprintf(stderr, "Complete packet recieved chan: %hhu command: %hhu len: %hu\n", 
    //        p->hdr.channel, p->hdr.command, p->hdr.body_len);
    switch(p->hdr.command) {
    case OPC_PIXEL_DATA:
        assert(p->hdr.body_len <= (STRAND_LEN * 3));
        int startch, endch;
        if (p->hdr.channel == 0) {
            startch = 0;
            endch = 16; // half open range
        } else {
            startch = p->hdr.channel - 1;
            endch = p->hdr.channel;
        }
        uv_mutex_lock(&pru_lock);
        for (int ch = startch; ch < endch; ch++) {
            memcpy(prus[0].rgb_fb[ch], p->body, p->hdr.body_len);
        }
        uv_mutex_unlock(&pru_lock);
        // TODO this
        break;
    case OPC_TEST:
        printf("Testing PRU 0\n");
        fflush(stdout);
        for (int i = 0; i < 64; i++) {
            uv_mutex_lock(&pru_lock);
            for (int ch = 0; ch < 16; ch++) {
                for (int led = 0; led < STRAND_LEN; led++) {
                    prus[0].rgb_fb[ch][led].r = i;
                    prus[0].rgb_fb[ch][led].g = i;
                    prus[0].rgb_fb[ch][led].b = i;
                }
            }
            //uint16_t* regbuf = calloc(sizeof(*regbuf), 500);
            //uint16_t nregs = translate_colors(regbuf, prus[0].rgb_fb, 10);
            //print_regbuf(regbuf, nregs);
            // display_thread does the actual displaying
            uv_mutex_unlock(&pru_lock);
            usleep(1000*25);
        }
        for (int ch = 0; ch < 16; ch++) {
            for (int led = 0; led < STRAND_LEN; led++) {
                prus[0].rgb_fb[ch][led].r = 0;
                prus[0].rgb_fb[ch][led].g = 0;
                prus[0].rgb_fb[ch][led].b = 0;
            }
        }
        break;
    case OPC_SYSEX:
        // what?
        break;
    }

    //printf("Done\n");
    fflush(stdout);
    free(p);
};

static void after_read(uv_stream_t* client,
					   ssize_t nread,
					   const uv_buf_t* uv_buf) {
    //printf("Got %d bytes.\n", nread);
    fflush(stdout);
	if (nread > 0) {
		struct opc_uv_data* uv_data = (struct opc_uv_data*)client->data;
		uv_mutex_lock(&(uv_data->lock));
		char* buf = uv_buf->base;
		while (nread > 0) {
			switch (uv_data->pkt_state) {
                case INIT:
				case COMPLETED:
					uv_data->pkt = malloc(sizeof(uv_data->pkt->hdr));
					if (nread < sizeof(uv_data->pkt->hdr)) {
						uv_data->pkt_state = PARTIAL_HDR;
						memcpy(uv_data->pkt, buf, nread);
						uv_data->pkt_sofar = nread;
						nread = 0;
						break;
						// done
					} else {
						// in this case we malloc and immediately realloc, which isn't great.
						uv_data->pkt_state = COMPLETED_HDR;
						memcpy(uv_data->pkt, buf, sizeof(uv_data->pkt->hdr));
						uv_data->pkt_sofar = sizeof(uv_data->pkt->hdr);
						buf += sizeof(uv_data->pkt->hdr);
						nread -= sizeof(uv_data->pkt->hdr);
						goto completed_hdr;
					}
				case PARTIAL_HDR:
					if (nread + uv_data->pkt_sofar < sizeof(uv_data->pkt->hdr)) {
						// header is still partial
						memcpy(uv_data->pkt_ptr + uv_data->pkt_sofar, buf, nread);
						uv_data->pkt_sofar += nread;
						nread = 0;
						break;
						// done
					} else {
						// we got the whole header, and we had part of it before. 
						uv_data->pkt_state = COMPLETED_HDR;
						size_t to_copy = sizeof(uv_data->pkt->hdr) - uv_data->pkt_sofar;
						memcpy(uv_data->pkt_ptr + uv_data->pkt_sofar, buf, to_copy);
						uv_data->pkt_sofar = sizeof(uv_data->pkt->hdr);
						buf += to_copy;
						nread -= to_copy;
						// fallthrough
					}
                completed_hdr:
				case COMPLETED_HDR:
					uv_data->pkt = realloc(uv_data->pkt, uv_data->pkt->hdr.body_len + sizeof(uv_data->pkt->hdr));
					uv_data->pkt_state = ALLOCATED;
					uv_data->pkt->hdr.body_len = ntohs(uv_data->pkt->hdr.body_len);
					// fallthrough
				case ALLOCATED:
					;
					size_t to_copy;
					if (nread + uv_data->pkt_sofar >= (sizeof(uv_data->pkt->hdr) + uv_data->pkt->hdr.body_len)) { // we got the end of the packet
						uv_data->pkt_state = COMPLETED;
						to_copy = uv_data->pkt->hdr.body_len - uv_data->pkt_sofar + sizeof(uv_data->pkt->hdr);
					} else {
						to_copy = nread;
						uv_data->pkt_sofar += nread;
					}
					memcpy(uv_data->pkt_ptr + uv_data->pkt_sofar, buf, to_copy);
					uv_data->pkt_sofar += to_copy;
					nread -= to_copy;
					buf += to_copy;
			}
            if (uv_data->pkt_state == COMPLETED) {
                struct opc_pkt* pkt = uv_data->pkt;
                uv_data->pkt = NULL;
                uv_data->pkt_state = INIT;
                uv_mutex_unlock(&(uv_data->lock));
                after_opc_packet(pkt); // after_opc_packet owns this memory now.
            } else {
                uv_mutex_unlock(&(uv_data->lock));
            }
		}
	} else if (nread < 0) {
		if (nread != UV_EOF) {
			fprintf(stderr, "read error %s\n", uv_strerror(nread));
		} else {
			fprintf(stdout, "client disconnected %s\n", uv_strerror(nread));
		}
		uv_close((uv_handle_t*)client, on_close);
	}
	free(uv_buf->base);
	/*
	   int r;
	   write_req_t* wr;
	   uv_shutdown_t* req;

	   if (nread <= 0 && buf->base != NULL)
	   free(buf->base);

	   if (nread == 0)
	   return;

	   if (nread < 0) {
	//assert(nread == UV_EOF);
	fprintf(stderr, "err: %s\n", uv_strerror(nread));

	req = (uv_shutdown_t*) malloc(sizeof(*req));
	assert(req != NULL);

	r = uv_shutdown(req, handle, after_shutdown);
	assert(r == 0);

	return;
	}

	data_cntr += nread;

	wr = (write_req_t*) malloc(sizeof(*wr));
	assert(wr != NULL);

	wr->buf = uv_buf_init(buf->base, nread);

	r = uv_write(&wr->req, handle, &wr->buf, 1, after_write);
	assert(r == 0);
	 */
}


static void alloc_cb(uv_handle_t* handle,
                     size_t suggested_size,
                     uv_buf_t* buf) {
    buf->base = malloc(suggested_size);
    assert(buf->base != NULL);
    buf->len = suggested_size;
}


static void on_connection(uv_stream_t* server, int status) {
	printf("Got a connection");
	uv_tcp_t* stream;
	int r;
    struct opc_uv_data* uv_data = calloc(sizeof(*uv_data), 1);
    uv_mutex_init(&uv_data->lock);

	assert(status == 0);

	stream = malloc(sizeof(uv_tcp_t));
	assert(stream != NULL);

	r = uv_tcp_init(uv_default_loop(), stream);
	assert(r == 0);

    stream->data = uv_data;

	r = uv_accept(server, (uv_stream_t*)stream);
	assert(r == 0);

	r = uv_read_start((uv_stream_t*)stream, alloc_cb, after_read);
	assert(r == 0);
}


static int tcp_echo_server() {
	uv_tcp_t* tcp_server;
	struct sockaddr_in addr;
	int r;

	r = uv_ip4_addr("0.0.0.0", PORT, &addr);
	assert(r == 0);

	tcp_server = (uv_tcp_t*) malloc(sizeof(*tcp_server));
	assert(tcp_server != NULL);

	r = uv_tcp_init(uv_default_loop(), tcp_server);
	assert(r == 0);

	r = uv_tcp_bind(tcp_server, (const struct sockaddr*)&addr, 0);
	assert(r == 0);

	r = uv_listen((uv_stream_t*)tcp_server, SOMAXCONN, on_connection);
	assert(r == 0);

	return 0;
}


int main() {
	printf("Starting\n");
	if (!init()) {
		printf("Failed to start PRUs. Reinstall firmware?\n");
		return 1;
	}
	printf("PRUs initialized\n");
	int r;

	r = tcp_echo_server();
	assert(r == 0);

    r = uv_thread_create(&display_thread, display_thread_main, NULL);
	assert(r == 0);

	r = uv_run(uv_default_loop(), UV_RUN_DEFAULT);
	assert(r == 0);

	return 0;
}
