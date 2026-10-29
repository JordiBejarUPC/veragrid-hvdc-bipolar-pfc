PSS/E 36 RAW Object Properties
==============================

Case Identification Data
------------------------
- Record 1: ``IC, SBASE``
- Record 2: heading line 1
- Record 3: heading line 2

Bus Data
--------
- Record: ``I, NAME, BASKV, IDE, AREA, ZONE, OWNER, VM, VA, NVHI, NVLO, EVHI, EVLO``

Load Data
---------
- Record: ``I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER, SCALE, INTRPT, DGENP, DGENQ, DGENM, LOADTYPE``

Fixed Bus Shunt Data
--------------------
- Record: ``I, ID, STATUS, GL, BL``

Generator Data
--------------
- Record: ``I, ID, PG, QG, QT, QB, VS, IREG, NREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT, RMPCT, PT, PB, BASLOD, O1, F1, O2, F2, O3, F3, O4, F4, WMOD, WPF``

Non-Transformer Branch Data
---------------------------
- Record: ``I, J, CKT, R, X, B, NAME, RATE1, RATE2, RATE3, RATE4, RATE5, RATE6, RATE7, RATE8, RATE9, RATE10, RATE11, RATE12, GI, BI, GJ, BJ, ST, MET, LEN, O1, F1, O2, F2, O3, F3, O4, F4``

System Switching Device Data
----------------------------
- Record: ``I, J, CKT, X, RATE1, RATE2, RATE3, RATE4, RATE5, RATE6, RATE7, RATE8, RATE9, RATE10, RATE11, RATE12, STATUS, NSTATUS, METERED, STYPE, NAME``

Transformer Data
----------------
- Line 1: ``I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, O1, F1, O2, F2, O3, F3, O4, F4, VECGRP, ZCOD``
- 2-winding line 2: ``R1_2, X1_2, SBASE1_2``
- 2-winding line 3: ``WINDV1, NOMV1, ANG1, RATE1_1, RATE1_2, RATE1_3, RATE1_4, RATE1_5, RATE1_6, RATE1_7, RATE1_8, RATE1_9, RATE1_10, RATE1_11, RATE1_12, COD1, CONT1, NODE1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1, CNXA1``
- 2-winding line 4: ``WINDV2, NOMV2``
- 3-winding line 2: ``R1_2, X1_2, SBASE1_2, R2_3, X2_3, SBASE2_3, R3_1, X3_1, SBASE3_1, VMSTAR, ANSTAR``
- 3-winding line 3: ``WINDV1, NOMV1, ANG1, RATE1_1, RATE1_2, RATE1_3, RATE1_4, RATE1_5, RATE1_6, RATE1_7, RATE1_8, RATE1_9, RATE1_10, RATE1_11, RATE1_12, COD1, CONT1, NODE1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1, CNXA1``
- 3-winding line 4: ``WINDV2, NOMV2, ANG2, RATE2_1, RATE2_2, RATE2_3, RATE2_4, RATE2_5, RATE2_6, RATE2_7, RATE2_8, RATE2_9, RATE2_10, RATE2_11, RATE2_12, COD2, CONT2, NODE2, RMA2, RMI2, VMA2, VMI2, NTP2, TAB2, CR2, CX2, CNXA2``
- 3-winding line 5: ``WINDV3, NOMV3, ANG3, RATE3_1, RATE3_2, RATE3_3, RATE3_4, RATE3_5, RATE3_6, RATE3_7, RATE3_8, RATE3_9, RATE3_10, RATE3_11, RATE3_12, COD3, CONT3, NODE3, RMA3, RMI3, VMA3, VMI3, NTP3, TAB3, CR3, CX3, CNXA3``

Area Interchange Data
---------------------
- Record: ``I, ISW, PDES, PTOL, ARNAME``

Two-Terminal DC Transmission Line Data
--------------------------------------
- Line 1: ``NAME, MDC, RDC, SETVL, VSCHD, VCMOD, RCOMP, DELTI, METER, DCVMIN, CCCITMX, CCCACC``
- Line 2: ``IPR, NBR, ANMXR, ANMNR, RCR, XCR, EBASR, TRR, TAPR, TMXR, TMNR, STPR, ICR, NDR, IFR, ITR, IDR, XCAPR``
- Line 3: ``IPI, NBI, ANMXI, ANMNI, RCI, XCI, EBASI, TRI, TAPI, TMXI, TMNI, STPI, ICI, NDI, IFI, ITI, IDI, XCAPI``

VSC DC Transmission Line Data
-----------------------------
- Line 1: ``NAME, MDC, RDC, O1, F1, O2, F2, O3, F3, O4, F4``
- Line 2: ``IBUS1, TYPE1, MODE1, DCSET1, ACSET1, ALOSS1, BLOSS1, MINLOSS1, SMAX1, IMAX1, PWF1, MAXQ1, MINQ1, VSREG1, NREG1, RMPCT1``
- Line 3: ``IBUS2, TYPE2, MODE2, DCSET2, ACSET2, ALOSS2, BLOSS2, MINLOSS2, SMAX2, IMAX2, PWF2, MAXQ2, MINQ2, VSREG2, NREG2, RMPCT2``

Transformer Impedance Correction Tables
---------------------------------------
- Header record: ``I``
- Point records: ``T, F`` pairs

Multi-Terminal DC Transmission Line Data
----------------------------------------
- Grouped records: DC line header, AC converter records, DC bus records, DC link records.

Multi-Section Line Grouping Data
--------------------------------
- Record: ``I, J, ID, MET, DUM1, DUM2, DUM3, DUM4, DUM5, DUM6, DUM7, DUM8, DUM9``

Zone Data
---------
- Record: ``I, ZONAME``

Interarea Transfer Data
-----------------------
- Record: ``I, ISW, PDES, PTOL, ARNAME``

Owner Data
----------
- Record: ``I, OWNAME``

FACTS Device Data
-----------------
- Record: ``NAME, I, J, MODE, PDES, QDES, VSET, SHMX, TRMX, VTMN, VTMX, VSMX, IMX, LINX, RMPCT, OWNER, SET1, SET2, VSREF, FCREG, NREG, MNAME``

Switched Shunt Data
-------------------
- Record: ``I, ID, MODSW, ADJM, STAT, VSWHI, VSWLO, SWREG, NREG, RMPCT, RMIDNT, BINIT, S1, N1, B1, S2, N2, B2, S3, N3, B3, S4, N4, B4, S5, N5, B5, S6, N6, B6, S7, N7, B7, S8, N8, B8``

GNE Device Data
---------------
- Present in manual family, current serializer returns an empty record set.

Induction Machine Data
----------------------
- Line 1: ``I, ID, STATUS, SCODE, DCODE, AREA, ZONE, OWNER, TCODE, BCODE, MBASE, RATEKV``
- Line 2: ``PCODE, PSET, H, A, B, D, E, RA, XA, XM, R1, X1, R2, X2, X3, E1, SE1, E2, SE2, IA1, IA2``
- Line 3: ``XAMULT``

Substation Data
---------------
- Record: ``IS, NAME, LATI, LONG, SGR``

Node Data
---------
- Record: ``ISUB, NI, NAME, I, STATUS, VM, VA``

Changes Relative to PSSE 36
---------------------------
- None.
