def write_params(mu, U, Nsample, filename, paramsfile="params.dat",
                 dtau="0.3d0", ds="0.3d-5", s_end="1d0"):
    with open(paramsfile, "w") as f:
        f.write(
            f"&params\n"
            f"mu = {mu}\n"
            f"U = {U}\n"
            f"dtau = {dtau}\n"
            f"ds = {ds}\n"
            f"s_end = {s_end}\n"
            f"datfilename = \"{filename}\"\n"
            f"/\n"
            f"&sampling_setting\n"
            f"Nsample = {Nsample}\n"
            f"/\n"
        )
