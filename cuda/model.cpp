// -*- coding: utf-8 -*-
/*
Copyright Landon Meernik
This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/
or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
*/

/*
ACHTUNG!
ALLES TURISTEN UND NONTEKNISCHEN LOOKENPEEPERS!
DAS KOMPUTERMASCHINE IST NICHT FUR DER GEFINGERPOKEN UND MITTENGRABEN!
ODERWISE IST EASY TO SCHNAPPEN DER SPRINGENWERK, BLOWENFUSEN UND POPPENCORKEN MIT SPITZENSPARKEN.
IST NICHT FUR GEWERKEN BEI DUMMKOPFEN.
DER RUBBERNECKEN SIGHTSEEREN KEEPEN DAS COTTONPICKEN HANDER IN DAS POCKETS MUSS.
ZO RELAXEN UND WATSCHEN DER BLINKENLICHTEN.
*/

#include <iostream>
#include <math.h>

struct Soma {
    // HH parameters
    const float Cm;       // uF/cm^2
    const float gbar_Na;  // mS/cm^2
    const float gbar_K;   // mS/cm^2
    const float gbar_l;   // mS/cm^2
    const float E_Na;     // mV
    const float E_K;      // mV
    const float E_l;      // mV
    const float const_I;  // Some fraction of amp
    // Dynamic properties
    float I;        // Some fraction of an amp
    float V;        // V
    float m;        // ItS FuCkInG MaGiC
    float n;
    float h;
    Soma(float const_I = 0,
         float V_zero  = -10,
         float Cm      = 1,
         float gbar_Na = 120,
         float gbar_K  = 36,
         float gbar_l  = 0.3,
         float E_Na    = 115,
         float E_K     = -12,
         float E_l     = 10.613):
        V(V_zero),
        I(0),
        Cm(Cm),
        gbar_Na(gbar_Na),
        gbar_K(gbar_K),
        gbar_l(gbar_l),
        E_Na(E_Na),
        E_K(E_K),
        E_l(E_l),
        const_I(const_I),
        m(this->alpha_m()/(this->alpha_m() + this->beta_m())),
        n(this->alpha_n()/(this->alpha_n() + this->beta_n())),
        h(this->alpha_h()/(this->alpha_h() + this->beta_h()))
    { /* yeet? */  }

    float alpha_n() const {
        return this->V != 10 ? 0.01 * (-this->V + 10) / (exp((-this->V + 10) / 10) - 1) : 0.1;
    }
    float beta_n() const {
        return 0.125 * exp(-this->V / 80);
    }
    float alpha_m() const {
        return this->V != 25 ? 0.1 * (-this->V + 25) / (exp((-this->V + 25) / 10) - 1) : 1;
    }
    float beta_m() const {
        return 4 * exp(-this->V / 18);
    }
    float alpha_h() const {
        return 0.07 * exp(-this->V / 20);
    }
    float beta_h() const {
        return 1 / (exp((-this->V + 30) / 10) + 1);
    }
    void step(float dT) {
        //Step the model by dT. Strange things may happen if you vary dT
        //this->I = sum([i.output() for i in this->inputs]);

        this->m += dT * (this->alpha_m() * (1 - this->m) - this->beta_m() * this->m);
        this->h += dT * (this->alpha_h() * (1 - this->h) - this->beta_h() * this->h);
        this->n += dT * (this->alpha_n() * (1 - this->n) - this->beta_n() * this->n);
        float g_Na = this->gbar_Na * pow(this->m, 3) * this->h;
        float g_K  = this->gbar_K * pow(this->n, 4);
        float g_l  = this->gbar_l;
        this->V += (this->const_I + this->I -
                   g_Na * (this->V - this->E_Na) -
                   g_K * (this->V - this->E_K) -
                   g_l * (this->V - this->E_l)) / this->Cm * dT;
    }
};

__global__
void add(int n, float *x, float *y)
{
    int index = threadIdx.x;
    int stride = blockDim.x;
    for (int i = index; i < n; i += stride) {
        y[i] = x[i] + y[i];
    }
}
/*
__global__
void step(float dT, int nsteps, int nsomas, Soma* somas) {
    int index = threadIdx.x;
    int stride = blockDim.x;
    for (int soma_idx = index; soma_idx < nsomas; soma_idx += stride) {
        for (int step_idx = 0; step_idx < nsteps; step++) {
            somas[soma_idx]->step(dT);
        }
    }
}
*/
int main(void)
{
    Soma s = new Soma();
    /*
    int N = 1<<20;
    float *x, *y;
    cudaMallocManaged(&x, N*sizeof(float));
    cudaMallocManaged(&y, N*sizeof(float));
    for (int i = 0; i < N; i++) {
        x[i] = 1.0f;
        y[i] = 2.0f;
    }
    add<<<1, 1>>>(N, x, y);
    cudaDeviceSynchronize();
    float maxError = 0.0f;
    for (int i = 0; i < N; i++) {
        maxError = fmax(maxError, fabs(y[i] - 3.0f));
    }
    std::cout << "Max error: " << maxError << std::endl;
    cudaFree(x);
    cudaFree(y);
    */
    return 0;
}
