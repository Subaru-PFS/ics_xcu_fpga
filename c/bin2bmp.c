#include <stdio.h>
#include <stdlib.h>

#define PIX_H 4240 // number of rows
#define PIX_W 536 // number of columns

#define DISCARD 10

unsigned char header[54] = {
	0x42, 0x4d, 0x36, 0x44, 0x40, 0x03, 0x00, 0x00,
	0x00, 0x00, 0x36, 0x00, 0x00, 0x00, 0x28, 0x00,
	0x00, 0x00, 0xc0, 0x10, 0x00, 0x00, 0x90, 0x10,
	0x00, 0x00, 0x01, 0x00, 0x18, 0x00, 0x00, 0x00,
	0x00, 0x00, 0x00, 0x44, 0x40, 0x03, 0x74, 0x12,
	0x00, 0x00, 0x74, 0x12, 0x00, 0x00, 0x00, 0x00,
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

unsigned short buf[PIX_H][8 * PIX_W];
unsigned long long means[8];

/* Each ADC is 1/8 of the image.  For each row of input,  we need to split it
 * into 8 sub-rows.  8 is the number of amplifiers, and I would rather write
 * "8" all over this program instead of "N_AMPS"
 */

int main (int argc, char **argv) {

	int i, j, k;
	unsigned short s;
	unsigned int red, green, blue; // false colors

	if (argc != 2) {
		fprintf(stderr,
		  "Usage: ./bin2bmp N < image.bin > image.bmp\n"
		  "N = 0 results in true image in green.\n"
		  "Higher N up to 16 adds more false color.\n"
		  );
		return -1;
	}

	// header:
	for (i=0; i!=54; i++) putchar(header[i]);

	// input
	for (i=0; i!=8; i++) means[i] = 0;
	for (k=0; k!=PIX_H; k++) {
		for (i=0; i!=PIX_W; i++) {
			for (j=0; j!=8; j++) {
				s = getchar();
				s |= getchar() << 8;
				buf[k][j * PIX_W + i] = s;
				means[j] += s;
			}
		}
	}

	// compute means:
	for (i=0; i!=8; i++) {
		means[i] = means[i]/(PIX_W);
		means[i] = means[i]/(PIX_H);
	}

	// output
	for (k=0; k!=PIX_H; k++) {
		for (i=0; i != 8; i++) {
			for (j=0; j != PIX_W; j++) {
				red = blue = 0;
				s = buf[k][i * PIX_W + j];
				green = s >> 8;
				if (s > means[i]) red = s - means[i];
				else blue = means[i] - s;
				red <<= strtoul(argv[1], 0, 0);
				blue <<= strtoul(argv[1], 0, 0);
				red >>= 8;
				blue >>= 8;
				if (red > 0xff) red = 0xff;
				if (blue > 0xff) blue = 0xff;

				putchar(blue);
				putchar(green);
				putchar(red);

				/*
				putchar(s & 0xff);
				putchar(s & 0xff);
				putchar(s & 0xff);
				*/
			}
		}
	}

	return 0;

}

