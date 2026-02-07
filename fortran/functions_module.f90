module functions_module
    use iso_fortran_env, only: real64, int32, error_unit
    use ieee_arithmetic, only: ieee_is_nan, ieee_is_finite
    implicit none

    logical :: is_converge

    integer(int32), parameter :: Ntau = 6, Nx = 6, Ny = 6, Nz = 6, Dx = Nx*Ny*Nz
    integer(int32), protected :: nn(6, Dx), idxtopos(3, Dx), postoidx(Nx, Ny, Nz)
    real(real64) :: mu, U, dtau, ds, s_end

    character(len=100) :: datfilename

    namelist /params/ mu, U, dtau, ds, s_end, datfilename

    complex(real64) :: a(Ntau, Dx), a_ast(Ntau, Dx)
    complex(real64), protected :: dw(Ntau, Dx)
contains

    subroutine make_pos_arrays()
        integer(int32) :: x, y, z, i
        i = 1
        do x = 1, Nx
            do y = 1, Ny
                do z = 1, Nz
                    idxtopos(1, i) = x
                    idxtopos(2, i) = y
                    idxtopos(3, i) = z
                    postoidx(x, y, z) = i
                    i = i + 1
                end do
            end do
        end do
    end subroutine

    subroutine set_nn()
        integer(int32) :: i, x, y, z

        call make_pos_arrays()
        do i = 1, Dx
            x = idxtopos(1, i)
            y = idxtopos(2, i)
            z = idxtopos(3, i)
            nn(1, i) = postoidx(modulo(x,   Nx) + 1, y, z) ! x+1
            nn(2, i) = postoidx(modulo(x-2, Nx) + 1, y, z) ! x-1
            nn(3, i) = postoidx(x, modulo(y,   Ny) + 1, z) ! y+1
            nn(4, i) = postoidx(x, modulo(y-2, Ny) + 1, z) ! y-1
            nn(5, i) = postoidx(x, y, modulo(z,   Nz) + 1) ! z+1
            nn(6, i) = postoidx(x, y, modulo(z-2, Nz) + 1) ! z-1
        end do
    end subroutine

    complex(real64) function da(a_in, a_ast_in, tau, x)! a, a_astからdaを計算
        integer(int32), intent(in) :: tau, x
        complex(real64), intent(in) :: a_in(:,:), a_ast_in(:,:)
        integer(int32) :: i

        da = a_in(modulo(tau, Ntau)+1, x)
        if ((tau-1) == 0) then ! tauが周期的なのでその処理
            da = da - a_in(Ntau, x)
        else
            da = da - a_in(tau-1, x)
        end if
        da = da / (2.0_real64 * dtau)
        do i = 1, 6
            da = da + a_in(tau, nn(i, x))
        end do
        da = da - U * a_ast_in(tau, x) * a_in(tau, x) * a_in(tau, x)
        da = da + mu * a_in(tau, x)
        da = 2.0_real64 * da
    end function

    complex(real64) function da_ast(a_in, a_ast_in, tau, x)!da_astを計算
        integer(int32), intent(in) :: tau, x
        complex(real64), intent(in) :: a_in(:,:), a_ast_in(:,:)
        integer(int32) :: i

        da_ast = a_ast_in(modulo(tau, Ntau)+1, x)
        if ((tau-1) == 0) then!tauが周期的なのでその処理
            da_ast = da_ast - a_ast_in(Ntau, x)
        else
            da_ast = da_ast - a_ast_in(tau-1, x)
        end if
        da_ast = -da_ast / (2.0_real64 * dtau)
        do i = 1, 6
            da_ast = da_ast + a_ast_in(tau, nn(i, x))
        end do
        da_ast = da_ast - U * a_ast_in(tau, x) * a_ast_in(tau, x) * a_in(tau, x)
        da_ast = da_ast + mu * a_ast_in(tau, x)
        da_ast = 2.0_real64 * da_ast
    end function

    subroutine set_dw()!dwにガウシアンノイズを代入 (Box-Muller, cos/sin両方を使用)
        integer(int32) :: i, j
        real(real64) :: X, Y, r, theta
        real(real64) :: pi
        pi = acos(-1.0_real64)
        do j = 1, Dx
            do i = 1, Ntau
                call random_number(X)
                call random_number(Y)
                X = max(X, epsilon(1.0_real64))  ! underflow保護: log(0)を防ぐ
                r = sqrt(-2.0_real64 * log(X))
                theta = 2.0_real64 * pi * Y
                dw(i, j) = cmplx(r * cos(theta), r * sin(theta), kind=real64)
            end do
        end do
    end subroutine

    subroutine initialize()
        real(real64) :: y
        y = sqrt((6.0_real64 + mu) / U)
        a = cmplx(y, 0.0_real64, kind=real64)
        a_ast = cmplx(y, 0.0_real64, kind=real64)
    end subroutine

    ! NaN または Inf を含むかチェックする補助関数
    logical function has_nan_or_inf(arr)
        complex(real64), intent(in) :: arr(:,:)
        integer(int32) :: i, j
        has_nan_or_inf = .false.
        do j = 1, size(arr, 2)
            do i = 1, size(arr, 1)
                if (ieee_is_nan(real(arr(i,j))) .or. ieee_is_nan(aimag(arr(i,j)))) then
                    has_nan_or_inf = .true.
                    return
                end if
                if (.not. ieee_is_finite(real(arr(i,j))) .or. &
                    .not. ieee_is_finite(aimag(arr(i,j)))) then
                    has_nan_or_inf = .true.
                    return
                end if
            end do
        end do
    end function

    subroutine do_langevin_loop_RK()! Langevin方程式を解く部分
        complex(real64) :: a_mid(Ntau, Dx), a_ast_mid(Ntau, Dx)
        complex(real64) :: a_next(Ntau, Dx), a_ast_next(Ntau, Dx)
        complex(real64) :: da_cache(Ntau, Dx), da_ast_cache(Ntau, Dx)
        real(real64) :: s, sigma
        integer(int32) :: x, tau
        sigma = sqrt(2.0_real64 * ds / dtau)

        s = 0.0_real64
        is_converge = .true.
        do while (s < s_end)
            s = s + ds
            call set_dw()
            ! 1st pass: drift を計算・キャッシュし、中間点を求める
            do x = 1, Dx
                do tau = 1, Ntau
                    da_cache(tau, x) = da(a, a_ast, tau, x)
                    da_ast_cache(tau, x) = da_ast(a, a_ast, tau, x)
                    a_mid(tau, x) = a(tau, x) + da_cache(tau, x) * ds + sigma * dw(tau, x)
                    a_ast_mid(tau, x) = a_ast(tau, x) + da_ast_cache(tau, x) * ds + sigma * conjg(dw(tau, x))
                end do
            end do
            ! 中間点の NaN/Inf チェック
            if (has_nan_or_inf(a_mid) .or. has_nan_or_inf(a_ast_mid)) then
                is_converge = .false.
                write(error_unit, '(A)') "ERROR: NaN/Inf detected in intermediate step (a_mid/a_ast_mid)"
                return
            end if
            ! 2nd pass: キャッシュ済みdrift を再利用
            do x = 1, Dx
                do tau = 1, Ntau
                    a_next(tau, x) = a(tau, x) + &
                        0.5_real64 * (da_cache(tau, x) + da(a_mid, a_ast_mid, tau, x)) * ds + sigma * dw(tau, x)
                    a_ast_next(tau, x) = a_ast(tau, x) + &
                        0.5_real64 * (da_ast_cache(tau, x) + da_ast(a_mid, a_ast_mid, tau, x)) * ds + sigma * conjg(dw(tau, x))
                end do
            end do
            ! 最終結果の NaN/Inf チェック
            if (has_nan_or_inf(a_next) .or. has_nan_or_inf(a_ast_next)) then
                is_converge = .false.
                write(error_unit, '(A)') "ERROR: NaN/Inf detected in final step (a_next/a_ast_next)"
                return
            end if
            a = a_next
            a_ast = a_ast_next
        end do
    end subroutine

    subroutine write_header(unit)
        integer(int32), intent(in) :: unit
        write(unit) Nx, U, mu, Ntau
    end subroutine

    subroutine write_body(unit)
        integer(int32), intent(in) :: unit
        complex(real64) :: arr1(Nx), arr2(Nx)
        integer(int32) :: i
        do i = 1, Nx
            arr1(i) = a(1, i)
            arr2(i) = a_ast(1, i)
        end do
        write(unit) arr1, arr2
    end subroutine
end module
