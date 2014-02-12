# CPL used c99 features, sorry.
CFLAGS = -g -O2 --std=c99 -Wall

all: test_image

test_image: bee_mem_file.h test_image.o libfpga.so
	$(CC) $(CFLAGS) test_image.o -L. -lfpga -o test_image

libfpga.so: fpga.c
	$(CC) -shared -fPIC $(CFLAGS) $< -o $@

# Probe for this machine's FPGA BAR0 access file.
# Note that this _always_ probes.
bee_mem_file.h::
	@echo "NOTE: regenerating bee_mem_file.h by probing the current machine. This will _only_ work on a BEE FPGA+CPU board!"
	@( \
	PROBED_FILENAME=`get_fpga_mmap_file.sh`; \
	if test -z "$${PROBED_FILENAME}"; then \
		echo "could not find FPGA on bus, using default value!" >&2 ; \
		cp bee_mem_file.h-in bee_mem_file.h ; \
	else \
	        ( echo "#define PROBED_FILENAME \"$${PROBED_FILENAME}\"" ; \
	      	  cat bee_mem_file.h-in ;\
                ) > bee_mem_file.h; \
		echo "using new probed FPGA file: $${PROBED_FILENAME}" >&2 ; \
	fi; \
	)

clean:
	rm -f *.o *.so *.S *.s *~
	rm -f test_image bee_mem_file.h
