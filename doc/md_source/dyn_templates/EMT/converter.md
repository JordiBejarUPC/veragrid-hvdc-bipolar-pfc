# Converter

This page summarizes the EMT converter model family and the available converter variants.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Parameter | `Ideal converter` | Averaged EMT converter template that synthesizes abc current from power commands and enforces DC power balance | template name |
| Parameter | `Full pseudo converter` | Averaged EMT converter template with explicit PLL, outer-loop, inner-loop, and interface subblocks | template name |
| Parameter | `Switched converter` | Hybrid EMT converter template that starts averaged and then enables explicit switching | template name |
| Parameter | `VSC Grid-Forming (GFM)` | EMT grid-forming converter template represented by an internal source behind an RL branch | template name |
