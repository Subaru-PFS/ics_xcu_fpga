# CPL used c99 features, sorry.
CFLAGS = -g -O3 --std=c99 -Wall -D_DEFAULT_SOURCE

all: libfpga.so reread

reread: bee_mem_file.h fpga.h reread.o libfpga.so
	$(CC) $(CFLAGS) reread.o -L. -lfpga -o reread

reread.o: fpga.h

readtest: bee_mem_file.h fpga.h readtest.o libfpga.so
	$(CC) $(CFLAGS) readtest.o -L. -lfpga -o readtest

readtest.o: fpga.h

fifotest: bee_mem_file.h fpga.h fifotest.o libfpga.so
	$(CC) $(CFLAGS) fifotest.o -L. -lfpga -o fifotest

fifotest.o: fpga.h

peekpoke: bee_mem_file.h fpga.h peekpoke.o libfpga.so
	$(CC) $(CFLAGS) peekpoke.o -L. -lfpga -o peekpoke

peekpoke.o: fpga.h

test_image: bee_mem_file.h fpga.h test_image.o libfpga.so
	$(CC) $(CFLAGS) test_image.o -L. -lfpga -o test_image

test_image.o: fpga.h

libfpga.so: fpga.c fpga.h bee_mem_file.h
	$(CC) -shared -fPIC $(CFLAGS) $< -o $@

# Probe for this machine's FPGA BAR0 access file.
# Note that this _always_ probes.
bee_mem_file.h::
	@echo "NOTE: regenerating bee_mem_file.h by probing the current machine. This will _only_ work on a BEE FPGA+CPU board!"
	@( \
	PROBED_BUSID=`get_fpga_bus_id.sh`; \
	if test -z "$${PROBED_BUSID}"; then \
		echo "could not find FPGA on bus, using default value!" >&2 ; \
		cp bee_mem_file.h-in bee_mem_file.h ; \
	else \
	        ( echo "#define PFS_FPGA_BUSID \"$${PROBED_BUSID}\"" ; \
	      	  cat bee_mem_file.h-in ;\
                ) > bee_mem_file.h; \
		echo "using new probed FPGA file: /sys/bus/pci/devices/$${PROBED_BUSID}/resource0" >&2 ; \
	fi; \
	)

clean:
	rm -f *.o *.so *.S *.s *~
	rm -f bee_mem_file.h
	rm -f test_image take_image 
	rm -f fiford fifowr summary
