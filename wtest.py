"""
python3.7
Created on Fri Sep 13 20:35:18 2019
@author:Hiroshi
"""
def write_params(mu, U, Nsample):
    file = open("params.dat", "w")
#    mu, U, Nsample = 12, 30, 100

    datstring = f"&params\n"+ f"mu = {mu}\n"+ f"U = {U}\n"+ f"dtau = 0.3d0\n"+ f"ds = 0.3d-4\n"+ f"s_end = 1d0\n"+ f"datfilename = \"data.dat\"\n/\n"+ f"&sampling_setting\n"+ f"Nsample = {Nsample}\n/"
    file.write(datstring)
    file.close
