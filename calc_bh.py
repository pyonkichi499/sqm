import scipy as sp
import matplotlib.pyplot as plt
from subprocess import run

# fortranで作ったdatファイルを読み込むのに使う(やつだったと思うけど要確認)
import read_dat_mod
# params.datの書き込みに使う
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

    # params.datのファイル名
    filename = f"U={U}," + f"s={s}" + ".dat"
    wparams.write_params(mu, U, Nsample, filename)
    run(["./a.out","params.dat"])
    corr_a_list.append(read_dat_mod.readfile(filename)[0])
    corr_a_list.append(read_dat_mod.readfile(filename)[1])

plt.close()
plt.error(U_list, corr_a_list, corr_err)
plt.savefig(f"U={U_0}"+"~"+f"{U_end},"+f"N={Nsample}"+".png")
