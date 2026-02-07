def write_params(mu, U, Nsample, filename, paramsfile="params.dat"):
    file = open(paramsfile, "w")
#    mu, U, Nsample = 12, 30, 100
    s = "1d0"
    ds = "0.3d-5"
    datstring = f"&params\n"+ f"mu = {mu}\n"+ f"U = {U}\n"+ f"dtau = 0.3d0\n"+ f"ds = {ds}\n"+ f"s_end = {s}\n"+ f"datfilename = \"{filename}\"\n/\n"+ f"&sampling_setting\n"+ f"Nsample = {Nsample}\n/\n"
    file.write(datstring)
    file.close()
