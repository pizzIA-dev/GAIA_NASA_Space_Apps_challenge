# Cobertura de IC 95 % y error tipo I (α = 0,05) del motor `trend_core`

Generado por `scripts/coverage_study.py` (1000 repeticiones base; 194 s). Ruido AR(1) gaussiano con coeficiente φ. Nominal: cobertura 95 %, error tipo I 5 %. Error de Monte Carlo ≈ ±1,4 pp con 1000 repeticiones y ±3 pp con 200.

| Serie | Método | φ | Repeticiones | Cobertura IC 95 % | Error tipo I |
|---|---|---|---|---|---|
| anual n=22 | OLS + IC clásico + t | 0.0 | 1000 | 95.8% | 4.4% |
| anual n=22 | OLS + IC clásico + t | 0.3 | 1000 | 87.7% ⚠ | 14.5% ⚠ |
| anual n=22 | OLS + IC clásico + t | 0.6 | 1000 | 67.4% ⚠ | 32.6% ⚠ |
| anual n=22 | OLS + IC HAC + t HAC | 0.0 | 1000 | 82.7% ⚠ | 12.8% ⚠ |
| anual n=22 | OLS + IC HAC + t HAC | 0.3 | 1000 | 80.2% ⚠ | 20.8% ⚠ |
| anual n=22 | OLS + IC HAC + t HAC | 0.6 | 1000 | 66.3% ⚠ | 32.9% ⚠ |
| anual n=22 | Theil–Sen + IC analítico + MK | 0.0 | 1000 | 95.4% | 4.1% |
| anual n=22 | Theil–Sen + IC analítico + MK | 0.3 | 1000 | 89.3% ⚠ | 13.2% ⚠ |
| anual n=22 | Theil–Sen + IC analítico + MK | 0.6 | 1000 | 71.1% ⚠ | 29.7% ⚠ |
| anual n=22 | OLS + IC n efectivo AR(1) + t AR(1) [nuevo] | 0.0 | 1000 | 96.5% | 2.8% |
| anual n=22 | OLS + IC n efectivo AR(1) + t AR(1) [nuevo] | 0.3 | 1000 | 93.9% | 6.6% |
| anual n=22 | OLS + IC n efectivo AR(1) + t AR(1) [nuevo] | 0.6 | 1000 | 89.3% ⚠ | 9.3% ⚠ |
| anual n=22 | Theil–Sen + IC n efectivo + MK AR(1) [nuevo, defecto] | 0.0 | 1000 | 95.9% | 3.0% |
| anual n=22 | Theil–Sen + IC n efectivo + MK AR(1) [nuevo, defecto] | 0.3 | 1000 | 93.8% | 6.7% |
| anual n=22 | Theil–Sen + IC n efectivo + MK AR(1) [nuevo, defecto] | 0.6 | 1000 | 86.9% ⚠ | 9.0% ⚠ |
| anual n=22 | Theil–Sen + bootstrap bloques (pares) + MK AR(1) [corregido] | 0.0 | 250 | 97.6% | 3.2% |
| anual n=22 | Theil–Sen + bootstrap bloques (pares) + MK AR(1) [corregido] | 0.3 | 250 | 96.4% | 9.6% ⚠ |
| anual n=22 | Theil–Sen + bootstrap bloques (pares) + MK AR(1) [corregido] | 0.6 | 250 | 89.6% ⚠ | 8.0% |
| mensual n=264 | OLS + IC clásico + t | 0.0 | 250 | 96.0% | 5.6% |
| mensual n=264 | OLS + IC clásico + t | 0.5 | 250 | 74.4% ⚠ | 24.0% ⚠ |
| mensual n=264 | OLS + IC HAC + t HAC | 0.0 | 250 | 96.0% | 6.4% |
| mensual n=264 | OLS + IC HAC + t HAC | 0.5 | 250 | 91.6% ⚠ | 9.6% ⚠ |
| mensual n=264 | Theil–Sen + IC analítico + MK | 0.0 | 250 | 96.8% | 5.6% |
| mensual n=264 | Theil–Sen + IC analítico + MK | 0.5 | 250 | 76.0% ⚠ | 22.0% ⚠ |
| mensual n=264 | OLS + IC n efectivo AR(1) + t AR(1) [nuevo] | 0.0 | 250 | 96.4% | 5.6% |
| mensual n=264 | OLS + IC n efectivo AR(1) + t AR(1) [nuevo] | 0.5 | 250 | 96.0% | 3.6% |
| mensual n=264 | Theil–Sen + IC n efectivo + MK AR(1) [nuevo, defecto] | 0.0 | 250 | 96.8% | 5.6% |
| mensual n=264 | Theil–Sen + IC n efectivo + MK AR(1) [nuevo, defecto] | 0.5 | 250 | 96.0% | 4.0% |

⚠ = cobertura < 92 % o error tipo I > 8 %. Theil–Sen + bootstrap en series mensuales no se midió (coste).
