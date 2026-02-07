program complex_Langevin_BH
    use functions_module
    implicit none

    integer :: i, Nsample, Nfailed
    character(len=60) :: arg

    namelist /sampling_setting/ Nsample

    ! 乱数シードをシステムのエントロピーから初期化
    ! (並列実行時に各プロセスが異なる乱数列を使う)
    ! 再現性が必要な場合は call random_seed(put=...) で固定値を設定する
    call random_seed()

    ! set_nn() の呼び出し
    ! idx, (x, y, z)の変換を行うための配列が定義される
    call set_nn()

    ! 実行時引数の読み取り
    call get_command_argument(1, arg)
    if (len_trim(arg) == 0) then
        stop "parameter file is required."
    end if

    ! 実行時引数で与えられた(params.dat)を開く
    open(11, file=trim(arg), status='old', action='read')
    ! (params.datの)&params部分を読み込む
    read(11, nml=params)
    ! &sampling_setting部分を読み込む
    read(11, nml=sampling_setting)
    close(11)

    write(*, *) "mu, U, dtau, Ntau, ds, s_end, Nsample = ", mu, U, dtau, Ntau, ds, s_end, Nsample

    Nfailed = 0
    open(20, file=datfilename, form="unformatted")
    call write_header(20)
    do i = 1, Nsample
        call initialize()
        write(*, *) "sample: ", i, " / ", Nsample, Nfailed
        call do_langevin_loop_RK()
        if (is_converge) then
            call write_body(20)
        else
            Nfailed = Nfailed + 1
        end if
    end do
    close(20)
end program
