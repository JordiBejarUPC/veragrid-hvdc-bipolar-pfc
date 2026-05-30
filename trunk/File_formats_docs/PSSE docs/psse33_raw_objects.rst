PSS/E 33 RAW Object Properties
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
- Record: ``I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER, SCALE, INTRPT``

Fixed Bus Shunt Data
--------------------
- Record: ``I, ID, STATUS, GL, BL``

Generator Data
--------------
- Record: ``I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT, RMPCT, PT, PB, O1, F1, O2, F2, O3, F3, O4, F4, WMOD, WPF``

Non-Transformer Branch Data
---------------------------
- Record: ``I, J, CKT, R, X, B, RATE1, RATE2, RATE3, GI, BI, GJ, BJ, ST, MET, LEN, O1, F1, O2, F2, O3, F3, O4, F4``

System Switching Device Data
----------------------------
- Not defined in this profile.

Transformer Data
----------------
- Line 1: ``I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, O1, F1, O2, F2, O3, F3, O4, F4, VECGRP``
- 2-winding line 2: ``R1_2, X1_2, SBASE1_2``
- 2-winding line 3: ``WINDV1, NOMV1, ANG1, RATE1_1, RATE1_2, RATE1_3, COD1, CONT1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1, CNXA1``
- 2-winding line 4: ``WINDV2, NOMV2``
- 3-winding line 2: ``R1_2, X1_2, SBASE1_2, R2_3, X2_3, SBASE2_3, R3_1, X3_1, SBASE3_1, VMSTAR, ANSTAR``
- 3-winding line 3: ``WINDV1, NOMV1, ANG1, RATE1_1, RATE1_2, RATE1_3, COD1, CONT1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1, CNXA1``
- 3-winding line 4: ``WINDV2, NOMV2, ANG2, RATE2_1, RATE2_2, RATE2_3, COD2, CONT2, RMA2, RMI2, VMA2, VMI2, NTP2, TAB2, CR2, CX2, CNXA2``
- 3-winding line 5: ``WINDV3, NOMV3, ANG3, RATE3_1, RATE3_2, RATE3_3, COD3, CONT3, RMA3, RMI3, VMA3, VMI3, NTP3, TAB3, CR3, CX3, CNXA3``

Area Interchange Data
---------------------
- Record: ``I, ISW, PDES, PTOL, ARNAME``

Two-Terminal DC Transmission Line Data
--------------------------------------
- Line 1: ``NAME, MDC, RDC, SETVL, VSCHD, VCMOD, RCOMP, DELTI, METER, DCVMIN, CCCITMX, CCCACC``
- Line 2: ``IPR, NBR, ANMXR, ANMNR, RCR, XCR, EBASR, TRR, TAPR, TMXR, TMNR, STPR, ICR, IFR, ITR, IDR, XCAPR``
- Line 3: ``IPI, NBI, ANMXI, ANMNI, RCI, XCI, EBASI, TRI, TAPI, TMXI, TMNI, STPI, ICI, IFI, ITI, IDI, XCAPI``

VSC DC Transmission Line Data
-----------------------------
- Line 1: ``NAME, MDC, RDC, O1, F1, O2, F2, O3, F3, O4, F4``
- Line 2: ``IBUS1, TYPE1, MODE1, DCSET1, ACSET1, ALOSS1, BLOSS1, MINLOSS1, SMAX1, IMAX1, PWF1, MAXQ1, MINQ1, REMOT1, RMPCT1``
- Line 3: ``IBUS2, TYPE2, MODE2, DCSET2, ACSET2, ALOSS2, BLOSS2, MINLOSS2, SMAX2, IMAX2, PWF2, MAXQ2, MINQ2, REMOT2, RMPCT2``

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
- Record: ``NAME, I, J, MODE, PDES, QDES, VSET, SHMX, TRMX, VTMN, VTMX, VSMX, IMX, LINX, RMPCT, OWNER, SET1, SET2, VSREF, REMOT, MNAME``

Switched Shunt Data
-------------------
- Record: ``I, MODSW, ADJM, STAT, VSWHI, VSWLO, SWREM, RMPCT, RMIDNT, BINIT, N1, B1, N2, B2, N3, B3, N4, B4, N5, B5, N6, B6, N7, B7, N8, B8``

GNE Device Data
---------------
- Not defined in this profile.

Induction Machine Data
----------------------
- Not defined in this profile.

Substation Data
---------------
- Not defined in this profile.

Node Data
---------
- Record: ``ISUB, NI, NAME, I, STATUS, VM, VA``

Changes Relative to PSSE 36
---------------------------
- Load has no ``DGENP, DGENQ, DGENM, LOADTYPE``.
- Generator has no ``NREG, BASLOD``.
- Branch has ``RATE1..RATE3`` only and no branch ``NAME``.
- No system switching, GNE, induction machine, or substation categories.
- FACTS uses ``REMOT`` control field.
- Switched shunt uses ``SWREM`` and ``N/B`` pairs.
