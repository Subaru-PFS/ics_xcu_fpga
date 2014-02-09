#include <stdio.h>

#define DISCARD 10 // number of initial pixels to ignore

#define PIX_H 4240 // number of rows
#define PIX_W 536 // number of columns

unsigned short mins[8][10];
unsigned short maxes[8][10];
unsigned long long sums[8];

/* This program summarizes the data for each of the 8 amplifiers.
 */

int main (void) {

	int i, j, k;
	unsigned short s;
	float f;

	for (i=0; i!=8; i++) {
		for (j=0; j!=10; j++) {
			mins[i][j] = 0xffff;
			maxes[i][j] = 0;
		}
		sums[i] = 0;
	}

	for (i=0; i!=PIX_H*PIX_W; i++) {
		for(j=0; j!=8; j++) {
			s = getchar();
			s |= getchar() << 8;
			//printf("s=0x%x\n", s);
			// maxes[j][0] is the highest
			if (s > maxes[j][9]) {
				maxes[j][9] = s;
				for (k=9; k!=0; k--) {
					if (s > maxes[j][k-1]) {
						maxes[j][k] = maxes[j][k-1];
						maxes[j][k-1] = s;
					}
				}
			}
			// mins[j][0] is the lowest
			if (s < mins[j][9]) {
				mins[j][9] = s;
				for (k=9; k!=0; k--) {
					if (s < mins[j][k-1]) {
						mins[j][k] = mins[j][k-1];
						mins[j][k-1] = s;
					}
				}
			}
			// do more analysis of s down here
			sums[j] += s;
		}
	}

	// output:
	for (i=0; i!=8; i++) {
		sums[i] = sums[i]/(PIX_H*PIX_W);
		printf("\nchannel %d maximums: ", i);
		for (j=0; j!=10; j++) printf(" %4x", maxes[i][j]);
		printf("\nchannel %d minimums: ", i);
		for (j=0; j!=10; j++) printf(" %4x", mins[i][j]);
		printf("\nchannel %d mean: %4x", i, sums[i]);
		printf(" decimal: %d", sums[i]);
		f = maxes[i][9];
		f = f - sums[i];
		f = f*100/sums[i];
		printf(" max: +%1.2f%%", f);
		f = mins[i][9];
		f = sums[i] - f;
		f = f*100/sums[i];
		printf(" min: -%1.2f%%", f);
	}
	printf("\n");

	return 0;
}

