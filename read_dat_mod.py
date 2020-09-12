import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import seaborn
seaborn.set(style="darkgrid", font_scale=1.5)
matplotlib.use("Agg")

def read_dat(filename):
    head, tail = ('head', '<i'), ('tail', '<i')
    header_dtype = np.dtype([
        head,
        ('Nx', '<i'),
        ('U', '<f8'),
        ('mu', '<f8'),
        tail])
    fd = open(filename, 'r')
    header = np.fromfile(fd, dtype=header_dtype, count=1)
    Nx = header[0]['Nx']
    #print(header)
    body_dtype = np.dtype([
        head,
        ('a', '<{}c16'.format(Nx)),
        ('a_ast', '<{}c16'.format(Nx)),
        tail])
    body = np.fromfile(fd, dtype=body_dtype, count=-1)
    return header, body


def jackknife(arr):
    n = len(arr)
    jk_mean = []
    for i in range(n):
        v = 0
        for j in range(n):
            if i != j:
                v += np.real(arr[j])
        jk_mean.append(1 / (n-1) * v)
    jk_mm = np.real(sum(arr)) / n
    var = 0
    for i in range(n):
        var += (jk_mean[i] - jk_mm)**2 / n
    err = np.sqrt((n - 1) * var)
    return jk_mm, err


def readfile(filename):
#filename = sys.argv[1]
#filename = "data1.dat"
    header, body = read_dat(filename)
    a_list = []
    a_ast_list = []
    N = len(body)
    for b in body:
        a_list.append(b['a'])
        a_ast_list.append(b['a_ast'])


#追記
#Ntau = header[0]["Ntau"]
    Ntau = 6
    U = header[0]["U"]
    mu = header[0]["mu"]
    Nx = header[0]['Nx']
    xarr = np.zeros(Nx)
    corr_mean = np.zeros(Nx, np.float)
    corr_err = np.zeros(Nx, np.float)

    for x in range(Nx):
        # print(x)
        corr_arr = []
        for i in range(N):
            a, a_ast = a_list[i], a_ast_list[i]
            def corr(a, a_ast, x):
                return a[0] * a_ast[x]
            corr_arr.append(np.real(corr(a, a_ast, x)))
        xarr[x] = x
        corr_mean[x], corr_err[x] = jackknife(corr_arr)
    print("num. of samples: {}".format(N))
    plt.close()
    plt.figure(dpi = 100)
    plt.title(f"$\mu$={mu:.1f}, U={U:.1f}")
    plt.ylabel("<$a_0a_i^*>$")
    plt.xlabel("$i$")

    plt.errorbar(xarr, corr_mean, yerr=corr_err)
    #plt.savefig("../figures/"+f"mu={mu:.1f},U={U:.1f},N={N}"+".png", bbox_inches="tight", pad_inches=0.0)
    plt.savefig("../figures/"+f"mu={mu:.1f},U={U:.1f},tau={Ntau:.0f},N={N}"+".png", bbox_inches="tight", pad_inches=0.0)
#    plt.show()
    return corr_mean[Nx//2]
