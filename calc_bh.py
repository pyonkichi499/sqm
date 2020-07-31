"""
python3.7
Created on Tue Sep 17 19:25:32 2019
@author:Hiroshi
"""

import scipy as sp
import matplotlib.pyplot as plt
from subprocess import run

import read_dat_mod
import wparams

U_0 = 5
U_end = 40
s = "1d0" # used only filename
Nsample = 200
U_list = sp.arange(U_0, U_end, 10)
corr_a_list = []
corr_err = []

for U in U_list:
    mu = 0.4*U
    filename = f"U={U}," + f"s={s}" + ".dat"
    wparams.write_params(mu, U, Nsample, filename)
    #run(["./a.out","params.dat"])
    corr_a_list.append(read_dat_mod.readfile(filename)[0])
    corr_a_list.append(read_dat_mod.readfile(filename)[1])

plt.close()
plt.error(U_list, corr_a_list, corr_err)
plt.savefig(f"U={U_0}"+"~"+f"{U_end},"+f"N={Nsample}"+".png")
