# Copyright 2017 Landon Meernik. Beerware license 

CLPRU=clpru
CLPRU_CFLAGS=-v3 -O2 --display_error_number --emit_warnings_as_errors
CLPRU_LFLAGS=--reread_libs --warn_sections --stack_size=0x100 --heap_size=0x100
CLPRU_INCLUDES=--include_path=/usr/lib/ti/pru-software-support-package/include --include_path=/usr/lib/ti/pru-software-support-package/include/am335x --include_path=/usr/share/ti/cgt-pru/include
CLPRU_LIBS=-i/usr/share/ti/cgt-pru/lib -i/usr/share/ti/cgt-pru/include 

.PHONY: clean loadfw install startpru restartpru magic

firmware: build/am335x-pru0-fw build/am335x-pru1-fw

install: build/am335x-pru0-fw build/am335x-pru1-fw
	cp build/am335x-pru0-fw /lib/firmware/am335x-pru0-fw
	cp build/am335x-pru1-fw /lib/firmware/am335x-pru1-fw
	$(MAKE) restartpru

magic: install
	./fuck.py 0 --len 300

build:
	mkdir build
clean:
	rm -r build || true

# -z changes the compiler into the linker. ~~MAGIC~~
build/am335x-pru0-fw: build/am335x-pru0-fw.obj  
	$(CLPRU) $(CLPRU_CFLAGS) -z  $(CLPRU_LIBS) $(CLPRU_LFLAGS) -obuild/am335x-pru0-fw build/am335x-pru0-fw.obj AM335x_PRU.cmd --library=libc.a --library=/usr/lib/ti/pru-software-support-package/lib/rpmsg_lib.lib

build/am335x-pru1-fw: build/am335x-pru1-fw.obj  
	$(CLPRU) $(CLPRU_CFLAGS) -z  $(CLPRU_LIBS) $(CLPRU_LFLAGS) -obuild/am335x-pru1-fw build/am335x-pru1-fw.obj AM335x_PRU.cmd --library=libc.a --library=/usr/lib/ti/pru-software-support-package/lib/rpmsg_lib.lib

build/am335x-pru0-fw.obj: pru_main.c resource_table.h build
	$(CLPRU) -DPRU_NO=0 $(CLPRU_INCLUDES) $(CLPRU_CFLAGS) -febuild/am335x-pru0-fw.obj ./pru_main.c 
build/am335x-pru1-fw.obj: pru_main.c resource_table.h build
	$(CLPRU) -DPRU_NO=1 $(CLPRU_INCLUDES) $(CLPRU_CFLAGS) -febuild/am335x-pru1-fw.obj ./pru_main.c 

build/campd: campd.c
	$(CC) -g3 -ggdb -std=gnu99 -Werror campd.c -o build/campd -luv

restartpru:  # If it's not already started, the write to unbind will fail
	echo "4a338000.pru1" > /sys/bus/platform/drivers/pru-rproc/unbind || true
	echo "4a334000.pru0" > /sys/bus/platform/drivers/pru-rproc/unbind || true
	echo "4a338000.pru1" > /sys/bus/platform/drivers/pru-rproc/bind
	echo "4a334000.pru0" > /sys/bus/platform/drivers/pru-rproc/bind
