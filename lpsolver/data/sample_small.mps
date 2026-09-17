NAME          SAMPLE1
ROWS
 N  COST
 L  LIM1
 L  LIM2
 G  LIM3
COLUMNS
    X1        COST      2.0        LIM1      1.0
    X1        LIM2      1.0        LIM3      1.0
    X2        COST      3.0        LIM1      2.0
    X2        LIM3      1.0
    X3        COST      1.0        LIM2      1.0
    X3        LIM3      1.0
RHS
    RHS       LIM1      10.0       LIM2      8.0
    RHS       LIM3      3.0
BOUNDS
 UP BND       X1        6.0
 UP BND       X2        6.0
 UP BND       X3        6.0
ENDATA
