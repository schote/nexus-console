"""Implementation of gradient operator."""
# %%
from console.utilities.reconstruction.abstract_operator import Operator
from functools import partial
import torch


class GradOperators(torch.nn.Module, Operator):
    @staticmethod
    def diff_kernel(ndim, mode):
        if mode == "doublecentral":
            kern = torch.tensor((-1, 0, 1))
        elif mode == "central":
            kern = torch.tensor((-1, 0, 1)) / 2
        elif mode == "forward":
            kern = torch.tensor((0, -1, 1))
        elif mode == "backward":
            kern = torch.tensor((-1, 1, 0))
        else:
            raise ValueError(f"mode should be one of (central, forward, backward, doublecentral), not {mode}")
        kernel = torch.zeros(ndim, 1, *(ndim * (3,)))
        for i in range(ndim):
            idx = tuple([i, 0, *(i * (1,)), slice(None), *((ndim - i - 1) * (1,))])
            kernel[idx] = kern
        return kernel

    def __init__(self, dim:int=2, mode:str="doublecentral", padmode:str = "circular"):
        """
        An Operator for finite Differences / Gradients
        Implements the forward as apply_G and the adjoint as apply_GH.
        
        Args:
            dim (int, optional): Dimension. Defaults to 2.
            mode (str, optional): one of doublecentral, central, forward or backward. Defaults to "doublecentral".
            padmode (str, optional): one of constant, replicate, circular or refelct. Defaults to "circular".
        """
        super().__init__()
        self.register_buffer("kernel", self.diff_kernel(dim, mode), persistent=False)
        self._dim = dim
        self._conv = (torch.nn.functional.conv1d, torch.nn.functional.conv2d, torch.nn.functional.conv3d)[dim - 1]
        self._convT = (torch.nn.functional.conv_transpose1d, torch.nn.functional.conv_transpose2d, torch.nn.functional.conv_transpose3d)[dim - 1]
        self._pad = partial(torch.nn.functional.pad, pad=2 * dim * (1,), mode=padmode)
        if mode == 'central':
            self._norm = (self.dim) ** (1 / 2)
        else:
            self._norm = (self.dim * 4) ** (1 / 2)

    @property
    def dim(self):
        return self._dim
    
    def fwd(self, x):
        """
        Forward
        """
        if x.is_complex():
            xr = torch.view_as_real(x).moveaxis(-1, 0)
        else:
            xr = x
        xr = xr.reshape(-1, 1, *x.shape[-self.dim :])
        xp = self._pad(xr)
        y = self._conv(xp, weight=self.kernel, bias=None, padding=0)
        if x.is_complex():
            y = y.reshape(2, *x.shape[: -self.dim], self.dim, *x.shape[-self.dim :])
            y = torch.view_as_complex(y.moveaxis(0, -1).contiguous())
        else:
            y = y.reshape(*x.shape[0 : -self.dim], self.dim, *x.shape[-self.dim :])
        return y

    def adj(self, x: torch.Tensor) -> torch.Tensor:
        """
        Adjoint
        """
        if x.is_complex():
            xr = torch.view_as_real(x).moveaxis(-1, 0)
        else:
            xr = x
        xr = xr.reshape(-1, self.dim, *x.shape[-self.dim :])
        xp = self._pad(xr)
        y = self._convT(xp, weight=self.kernel, bias=None, padding=2)
        if x.is_complex():
            y = y.reshape(2, *x.shape[: -self.dim - 1], *x.shape[-self.dim :])
            y = torch.view_as_complex(y.moveaxis(0, -1).contiguous())
        else:
            y = y.reshape(*x.shape[: -self.dim - 1], *x.shape[-self.dim :])
        return y
    
  
    def apply_adj_fwd(self, x: torch.Tensor) -> torch.Tensor:
        if x.is_complex():
            xr = torch.view_as_real(x).moveaxis(-1, 0)
        else:
            xr = x
        xr = xr.reshape(-1, 1, *x.shape[-self.dim :])
        xp = self._pad(xr)
        tmp = self._conv(xp, weight=self.kernel, bias=None, padding=0)
        tmp = self._pad(tmp)
        y = self._convT(tmp, weight=self.kernel, bias=None, padding=2)
        if x.is_complex():
            y = y.reshape(2, *x.shape)
            y = torch.view_as_complex(y.moveaxis(0, -1).contiguous())
        else:
            y = y.reshape(*x.shape)
        return y

# %%

# Revision using complex convolutions: Work in progress...

# class GradientOperator2D(Operator):
#     """
#     Gradient operator which implements forward and adjoint operation.
    
#     Operates on two-dimensional tensors of dimension (nx, ny)
#     """
    
#     def __init__(self, padding: int = 1):
#         """Initialization of 2D gradient operator.

#         Parameters
#         ----------
#         padding, optional
#             Padding size, by default 1
#         """
#         dx = torch.zeros((3, 3), dtype=torch.cfloat)
#         dy = torch.zeros((3, 3), dtype=torch.cfloat)
#         dx[1,:] = torch.tensor([0, 1+1j, -1-1j]) # forward differences
#         dy[:,1] = torch.tensor([0, 1+1j, -1-1j]) # forward differences
#         # dx[1,:] = torch.tensor([1+1j, 0, -1-1j]) # central differences
#         # dy[:,1] = torch.tensor([1+1j, 0, -1-1j]) # central differences
#         # Unsqueeze kernel to cover channel dimension
#         self.grad_kernel = torch.stack((dx, dy), dim=0).unsqueeze(1)
#         self.npad = padding

#     def fwd(self, data: torch.Tensor) -> torch.Tensor:
        
#         # Take only real part of kernel if data is real, complex otherwise
#         kernel = self.grad_kernel if data.is_complex() else self.grad_kernel.real
#         # Apply circular padding to input, data is extended by channel dimension
#         # Padding operator for 2d: (padding_left, padding_right, padding_top, padding_bottom)
#         padded_input = F.pad(data[None, ...], pad=[self.npad]*4, mode='circular')
#         # Apply 2D convolution, supports complex data
#         data_fwd = F.conv2d(padded_input, kernel, bias=None, padding=self.npad)
#         # Pad margins
#         data_fwd = data_fwd[..., self.npad:-self.npad, self.npad:-self.npad]

#         return data_fwd.squeeze()
        
#     def adj(self, data: torch.Tensor) -> torch.Tensor:
        
#         # Take only real part of kernel if data is real, complex otherwise
#         kernel = self.grad_kernel if data.is_complex() else self.grad_kernel.real
#         # Apply circular padding to input, data is extended by channel dimension
#         # Padding operator for 2d: (padding_left, padding_right, padding_top, padding_bottom)
#         padded_input = F.pad(data, pad=[self.npad]*4, mode='circular')
#         # Apply transpose 2D convolution, supports complex data
#         data_adj = F.conv_transpose2d(padded_input, kernel, bias=None, padding=self.npad)
#         # Pad margins
#         data_adj = data_adj[..., self.npad:-self.npad, self.npad:-self.npad]

#         return data_adj.squeeze()