module functions_module
    implicit none

    logical :: is_converge

    integer, parameter :: Ntau = 6, Nx = 6, Ny = 6, Nz = 6, Dx = Nx*Ny*Nz
    integer, protected :: nn(6, Dx), idxtopos(3, Dx), postoidx(Nx, Ny, Nz)
    double precision :: mu, U, dtau, ds, s_end

    character(len=100) :: datfilename

    namelist /params/ mu, U, dtau, ds, s_end, datfilename

    complex(kind(0d0)) :: a(Ntau, Dx), a_ast(Ntau, Dx)
    complex(kind(0d0)), protected :: dw(Ntau, Dx)
contains

    subroutine make_pos_arrays()
        integer :: x, y, z, i
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
        integer :: i, x, y, z

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

    complex(kind(0d0)) function da(a, a_ast, tau, x)! a, a_astからdaを計算
        integer :: tau, x, i
        complex(kind(0d0)), intent(in) :: a(:,:), a_ast(:,:)

        da = a(modulo(tau, Ntau)+1, x)
        if ((tau-1) == 0) then ! tauが周期的なのでその処理
            da = da - a(Ntau, x)
        else
            da = da - a(tau-1, x)
        end if
        da = da / (2d0 * dtau)
        do i = 1, 6
            da = da + a(tau, nn(i, x))
        end do
        da = da - U * a_ast(tau, x) * a(tau, x) * a(tau, x)
        da = da + mu * a(tau, x)
        da = 2d0 * da
    end function

    complex(kind(0d0)) function da_ast(a, a_ast, tau, x)!da_astを計算
        integer :: tau, x, i
        complex(kind(0d0)), intent(in) :: a(:,:), a_ast(:,:)

        da_ast = a_ast(modulo(tau, Ntau)+1, x)
        if ((tau-1) == 0) then!tauが周期的なのでその処理
            da_ast = da_ast - a_ast(Ntau, x)
        else
            da_ast = da_ast - a_ast(tau-1, x)
        end if
        da_ast = -da_ast / (2d0 * dtau)
        do i = 1, 6
            da_ast = da_ast + a_ast(tau, nn(i, x))
        end do
        da_ast = da_ast - U * a_ast(tau, x) * a_ast(tau, x) * a(tau, x)
        da_ast = da_ast + mu * a_ast(tau, x)
        da_ast = 2d0 * da_ast
    end function

    subroutine set_dw()!dwにガウシアンノイズを代入 (Box-Muller, cos/sin両方を使用)
        integer :: i, j
        double precision :: X, Y, r, theta
        double precision, parameter :: pi = 3.1415926535897932384626433832795028841971693d0
        do j = 1, Dx
            do i = 1, Ntau
                call random_number(X)
                call random_number(Y)
                r = sqrt(-2.0d0 * log(X))
                theta = 2.0d0 * pi * Y
                dw(i, j) = complex(r * cos(theta), r * sin(theta))
            end do
        end do
    end subroutine

    subroutine initialize()
        double precision :: y
        y = sqrt((6d0 + mu) / U)
        a = complex(y, 0d0)
        a_ast = complex(y, 0d0)
    end subroutine

    subroutine do_langevin_loop_RK()! Langevin方程式を解く部分
        complex(kind(0d0)) :: a_mid(Ntau, Dx), a_ast_mid(Ntau, Dx), a_next(Ntau, Dx), a_ast_next(Ntau, Dx)
        complex(kind(0d0)) :: da_cache(Ntau, Dx), da_ast_cache(Ntau, Dx)
        double precision :: s, sigma
        integer :: x, tau
        sigma = sqrt(2d0 * ds / dtau)

        s = 0d0
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
            ! 2nd pass: キャッシュ済みdrift を再利用
            do x = 1, Dx
                do tau = 1, Ntau
                    a_next(tau, x) = a(tau, x) + &
                        0.5d0 * (da_cache(tau, x) + da(a_mid, a_ast_mid, tau, x)) * ds + sigma * dw(tau, x)
                    a_ast_next(tau, x) = a_ast(tau, x) + &
                        0.5d0 * (da_ast_cache(tau, x) + da_ast(a_mid, a_ast_mid, tau, x)) * ds + sigma * conjg(dw(tau, x))
                    if ( isnan(real(a_next(tau, x))) .or. isnan(imag(a_next(tau, x))) ) then
                        is_converge = .false.
                        return
                    endif
                end do
            end do
            a = a_next
            a_ast = a_ast_next
        end do
    end subroutine

    subroutine write_header(unit)
        integer, intent(in) :: unit
        write(unit) Nx, U, mu, Ntau
    end subroutine

    subroutine write_body(unit)
        integer, intent(in) :: unit
        complex(kind(0d0)) :: arr1(Nx), arr2(Nx)
        integer :: i
        do i = 1, Nx
            arr1(i) = a(1, i)
            arr2(i) = a_ast(1, i)
        end do
        write(unit) arr1, arr2
    end subroutine
end module
