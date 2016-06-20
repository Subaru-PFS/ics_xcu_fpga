BIOS 
----

For a new, blank, out-of-the-box machine, we must connect VGA (CN10)
and the CN5 PS/2 plus reset board. This is to enable the serial
console and PXE booting, after which the BEE can be installed in a
pie-pan.

From the BIOS prompt, the following changes and/or checks are essential:

. 1x standard serial RS-232 ports on first port (COM1, for console)
. Configure console redirection, under Boot/Console Redirection. Set
  to COM1, IRQ4, 38400, No flow control, Always redirected, ANSI.
. Set the 1st boot device to the 1st Ethernet device.
. 2x standard serial RS-232 ports on second port (COM2/4)

. enable GbE WOL

Under Power/Advanced ACPI Configuration:
 . Set ACPI v3.0
 . Enable headless ACPI mode
 . Set MPS 1.4

You can also set the following, though this can be done later:

. enable speedstep, confirm c-states enabled
. boot display to VGA only
. lower dynamic video to 128M
. enable PCI E Active State Power Mgmt

. enable watchdog timer
. disable LCD
. disable PS/2 mouse

