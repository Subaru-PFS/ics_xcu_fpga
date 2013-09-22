/* This is a utility to convert a spreadsheet into a waveform binary.
 * It builds and runs in any Unix environment.  Building it is as simple as
 * gcc -Wall csv2bin.c -o csv2bin
 *
 * Running it is as simple as
 * ./csv2bin < waveform.csv > waveform.bin
 *
 * It won't work unless you generate a .csv file in the right format.  To do
 * that, start with the template we have and don't go crazy modifying it.
 * When it has the timing you want, save as a csv with comma field delimiters
 * and single quote text delimiters.
 *
 * The resulting .bin file will be used on the BEE by software that we have
 * yet to begin writing.
 */
#include <stdio.h>
#include <assert.h>
#define NROWS 16
#define MAX_COLS 2048

int main(void) {
	int column0 = 1;
	unsigned int times[MAX_COLS];
	int waveform[NROWS][MAX_COLS];
	int ncolumns = 0;
	int i, j, x, ret;
	char s[400];

	// Discard rows until we get to "counts from start"
	ret = 0;
	while (0 == ret) {
		scanf(" %[^\n]", s); // discard the rest of a row
		ret = scanf("\n'counts from start'%1s", s);
	}

	// Discard empty cells
	do {
		ret = scanf(",%d", times + ncolumns);
		//fprintf(stderr, "n=%d, t=%d\n", ncolumns, times[ncolumns]);
		column0++;
	} while (0 == ret);

	// Collect transition times
	do {
		ncolumns++;
		ret = scanf(",%d", times + ncolumns);
		//fprintf(stderr, "n=%d, t=%d\n", ncolumns, times[ncolumns]);
	} while (0 != ret);
	fprintf(stderr, "column 0=%d\n", column0);
	for (i=0; i<ncolumns; i++) fprintf(stderr, "t%d=%d\n", i, times[i]);

	// Discard another row
	scanf(" %[^\n]", s);

	// Read 16 rows with bit values
	for (i=0; i<NROWS; i++) {
		// Read row number
		assert(scanf(" %d,'", &x));
		fprintf(stderr, "row=%d\n", x);
		assert(x == i + 1);
		// Skip text cells
		for (j=1; j<column0; j++) scanf("%[^']','", s);
		// Read bit values
		for (j=0; j<ncolumns; j++) {
			//fprintf(stderr, "j=%d\n", j);
			assert(scanf("%d,", &x));
			assert((1 == x) || (0 == x));
			waveform[i][j] = x;
		}


	}

	// Write binary
	for (i=0; i<ncolumns; i++) {
		// values in times[] are converted into output values
		for (j=0; j<NROWS; j++) {
			if (waveform[j][i]) times[i] |= 1 << (j + 16);
		}
		putchar(times[i] & 0xff);
		putchar((times[i] >> 8) & 0xff);
		putchar((times[i] >> 16) & 0xff);
		putchar((times[i] >> 24) & 0xff);
	}

	return 0;

}
