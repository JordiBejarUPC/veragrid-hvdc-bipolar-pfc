PSS/E 31 RAW Object Properties (Chapter 3)
==========================================

Case Identification Data (3.2.1)
---------------------------------
- Record 1: ``IC, SBASE``
- Record 2: heading line 1
- Record 3: heading line 2

Bus Data (3.2.2)
----------------
- Record: ``I, NAME, BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER``

Load Data (3.2.3)
-----------------
- Record: ``I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER``

Generator Data (3.2.4)
----------------------
- Record: ``I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT, RMPCT, PT, PB, O1, F1, O2, F2, O3, F3, O4, F4``

Non-Transformer Branch Data (3.2.5)
------------------------------------
- Record: ``I, J, CKT, R, X, B, RATEA, RATEB, RATEC, GI, BI, GJ, BJ, ST, LEN, O1, F1, O2, F2, O3, F3, O4, F4``

Transformer Data (3.2.6)
-------------------------
- Line 1 (2w and 3w): ``I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, O1, F1, O2, F2, O3, F3, O4, F4``
- 2-winding line 2: ``R1_2, X1_2, SBASE1_2``
- 2-winding line 3: ``WINDV1, NOMV1, ANG1, RATA1, RATB1, RATC1, COD1, CONT1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1``
- 2-winding line 4: ``WINDV2, NOMV2``
- 3-winding line 2: ``R1_2, X1_2, SBASE1_2, R2_3, X2_3, SBASE2_3, R3_1, X3_1, SBASE3_1, VMSTAR, ANSTAR``
- 3-winding line 3: ``WINDV1, NOMV1, ANG1, RATA1, RATB1, RATC1, COD1, CONT1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1``
- 3-winding line 4: ``WINDV2, NOMV2, ANG2, RATA2, RATB2, RATC2, COD2, CONT2, RMA2, RMI2, VMA2, VMI2, NTP2, TAB2, CR2, CX2``
- 3-winding line 5: ``WINDV3, NOMV3, ANG3, RATA3, RATB3, RATC3, COD3, CONT3, RMA3, RMI3, VMA3, VMI3, NTP3, TAB3, CR3, CX3``

Area Interchange Data (3.2.8)
------------------------------
- Record: ``I, ISW, PDES, PTOL, ARNAME``

Two-Terminal DC Line Data (3.2.9)
----------------------------------
- Line 1: ``I, MDC, RDC, SETVL, VSCHD, VCMOD, RCOMP, DELTI, METER, DCVMIN, CCCITMX, CCCACC``
- Line 2: ``IPR, NBR, ALFMX, ALFMN, RCR, XCR, EBASR, TRR, TAPR, TMXR, TMNR, STPR, ICR, IFR, ITR, IDR, XCAPR``
- Line 3: ``IPI, NBI, GAMMX, GAMMN, RCI, XCI, EBASI, TRI, TAPI, TMXI, TMNI, STPI, ICI, IFI, ITI, IDI, XCAPI``

VSC DC Line Data (3.2.10)
-------------------------
- Line 1: ``NAME, MDC, RDC, O1, F1, O2, F2, O3, F3, O4, F4``
- Line 2 (converter 1): ``IBUS1, TYPE1, MODE1, DCSET1, ACSET1, ALOSS1, BLOSS1, MINLOSS1, SMAX1, IMAX1, PWF1, MAXQ1, MINQ1, REMOT1, RMPCT1``
- Line 3 (converter 2): ``IBUS2, TYPE2, MODE2, DCSET2, ACSET2, ALOSS2, BLOSS2, MINLOSS2, SMAX2, IMAX2, PWF2, MAXQ2, MINQ2, REMOT2, RMPCT2``

Switched Shunt Data (3.2.11)
----------------------------
- Record: ``I, MODSW, VSWHI, VSWLO, SWREM, RMPCT, RMIDNT, BINIT, N1, B1, N2, B2, N3, B3, N4, B4, N5, B5, N6, B6, N7, B7, N8, B8``

Transformer Impedance Correction Tables (3.2.12)
-------------------------------------------------
- Record: ``I, T1, F1, T2, F2, T3, F3, ..., T11, F11``

Multi-Terminal DC Line Data (3.2.13)
-------------------------------------
- Record group 1 (header): ``VCONV, VCONVN, NDCBS, NDCLN, MDC, VCONV2``
- Record group 2 (converter records, repeated ``VCONV`` times):
  ``IB, N, ANMXR, ANMNR, RCR, XCR, EBAS, TR, TAP, TMX, TMN, TSTP, SETVL, DCPF, MARG, CNVCOD``
- Record group 3 (dc bus records, repeated ``NDCBS`` times):
  ``IDC, IB, IA, ZONE, NAME, IDC2, RGRND, OWNER``
- Record group 4 (dc link records, repeated ``NDCLN`` times):
  ``IDC, JDC, DCCKT, RDC, LDC``

Multi-Section Line Grouping (3.2.14)
-------------------------------------
- Record: ``I, J, ID, DUM1, DUM2, DUM3, DUM4, DUM5, DUM6, DUM7, DUM8, DUM9``

Zone Data (3.2.15)
------------------
- Record: ``I, ZONAME``

Interarea Transfer Data (3.2.16)
---------------------------------
- Record: ``ARFROM, ARTO, TRID, PTRAN``

Owner Data (3.2.17)
-------------------
- Record: ``I, OWNAME``

FACTS Device Data (3.2.18)
--------------------------
- Record: ``N, I, J, MODE, PDES, QDES, VSET, SHMX, TRMX, VTMN, VTMX, VSMX, IMX, LINX, RMPCT, OWNER, SET1, SET2, VSREF``

Notes
-----
- This file reflects Chapter 3 of ``PSSE users manual v31.pdf``.
- Chapter 3 in v31 does not define independent RAW categories for fixed shunt, system switching device, GNE device, induction machine, substation, or node data.
