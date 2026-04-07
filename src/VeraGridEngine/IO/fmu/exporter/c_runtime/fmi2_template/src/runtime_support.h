#ifndef RUNTIME_SUPPORT_H
#define RUNTIME_SUPPORT_H

#include "../include/fmi2Functions.h"

#ifndef NAN
#define NAN (0.0 / 0.0)
#endif

#ifndef isnan
#define isnan(x) ((x) != (x))
#endif

void* calloc(size_t count, size_t size);
void free(void* ptr);
void* memset(void* ptr, int value, size_t count);
void* memcpy(void* dst, const void* src, size_t count);
size_t strlen(const char* text);

double fabs(double x);
double floor(double x);
double log(double x);
double sqrt(double x);
double sin(double x);
double cos(double x);
double tan(double x);
double exp(double x);
double asin(double x);
double acos(double x);
double atan(double x);
double atan2(double y, double x);
double sinh(double x);
double cosh(double x);
double fmin(double x, double y);
double fmax(double x, double y);

#endif
