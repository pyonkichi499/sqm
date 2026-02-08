program complex_Langevin_BH
    use functions_module
    use iso_fortran_env, only: error_unit
    implicit none

    integer :: i, Nsample, Nfailed
    integer :: ios
    character(len=256) :: iomsg_buf
    character(len=256) :: arg

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
        write(error_unit, '(A)') "ERROR: parameter file is required."
        stop 1
    end if

    ! 実行時引数で与えられた(params.dat)を開く
    open(11, file=trim(arg), status='old', action='read', &
         iostat=ios, iomsg=iomsg_buf)
    if (ios /= 0) then
        write(error_unit, '(A,A)') "ERROR: Failed to open parameter file: ", trim(iomsg_buf)
        stop 1
    end if

    ! (params.datの)&params部分を読み込む
    read(11, nml=params, iostat=ios, iomsg=iomsg_buf)
    if (ios /= 0) then
        write(error_unit, '(A,A)') "ERROR: Failed to read &params namelist: ", trim(iomsg_buf)
        close(11)
        stop 1
    end if

    ! &sampling_setting部分を読み込む
    read(11, nml=sampling_setting, iostat=ios, iomsg=iomsg_buf)
    if (ios /= 0) then
        write(error_unit, '(A,A)') "ERROR: Failed to read &sampling_setting namelist: ", trim(iomsg_buf)
        close(11)
        stop 1
    end if

    close(11, iostat=ios, iomsg=iomsg_buf)
    if (ios /= 0) then
        write(error_unit, '(A,A)') "WARNING: Failed to close parameter file: ", trim(iomsg_buf)
    end if

    write(*, *) "mu, U, dtau, Ntau, ds, s_end, Nsample = ", mu, U, dtau, Ntau, ds, s_end, Nsample

    Nfailed = 0
    open(20, file=datfilename, form="unformatted", iostat=ios, iomsg=iomsg_buf)
    if (ios /= 0) then
        write(error_unit, '(A,A)') "ERROR: Failed to open output file: ", trim(iomsg_buf)
        stop 1
    end if

    call write_header(20)
    do i = 1, Nsample
        call initialize()
        write(*, *) "sample: ", i, " / ", Nsample, Nfailed
        flush(6)
        call do_langevin_loop_RK()
        if (is_converge) then
            call write_body(20)
        else
            Nfailed = Nfailed + 1
        end if
    end do

    close(20, iostat=ios, iomsg=iomsg_buf)
    if (ios /= 0) then
        write(error_unit, '(A,A)') "WARNING: Failed to close output file: ", trim(iomsg_buf)
    end if
end program
