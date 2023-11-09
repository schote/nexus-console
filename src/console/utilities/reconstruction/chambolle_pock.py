
from console.utilities.reconstruction.gradient_operator import Operator, GradOperators
import torch 

def power_iteration(operator, x_0, niter = 36):
    """
    Power iteration to estimate the operator norm.
    
    Estimating the norm of A o D, where A is the forward encoding operator and D = \sum_k d_k \ast
    """
    with torch.no_grad():
        q_k = x_0
        for _ in range(niter):
            z_k = operator(q_k)
            z_k_norm = torch.sqrt(inner_product(z_k,z_k))   # calculate the norm
            q_k = z_k / z_k_norm    # re normalize the vector
        operator_q_k = operator(q_k)
        op_norm = torch.sqrt(inner_product(operator_q_k, operator_q_k).cpu())
    return op_norm


def inner_product(t1, t2):
	"""Calculate inner product, dependent on dtype."""
	if torch.is_complex(t1):
		innerp = torch.sum(t1.flatten() * t2.flatten().conj())
	else:
		innerp = torch.sum(t1.flatten() * t2.flatten())
	return innerp


def clip(x, threshold):
    """Clip data by threshold."""
    is_complex = x.is_complex()
    if is_complex:
        x = torch.view_as_real(x)
        threshold = threshold.unsqueeze(-1)
    x = torch.clamp(x, -threshold, threshold)
    if is_complex:
        x = torch.view_as_complex(x)
    return x


class ChambollePock:
    """Chambolle-Pock algorithm.
    
    DOI: 10.1007/s10851-010-0251-1
    """
    
    def __init__(self, operator: Operator) -> None:
        self.op = operator
        self.op_dif = GradOperators(dim=2, mode="forward")
    
    def __call__(
        self, 
        kspace: torch.Tensor, 
        x_0: torch.Tensor, 
        gamma: float = 0.05, 
        num_iterations: int = 200,
        theta: float = 1.0
        ) -> list[torch.Tensor]:
        """Apply chambolle pock algorithm

        Parameters
        ----------
        kspace
            k-space input data
        x_0
            Initial guess
        gamma, optional
            Regularization coefficient, by default 0.05
        num_iterations, optional
            Number of iterations, by default 200
        theta, optional
            Step size which should be between 0 and 1, by default 1.0

        Returns
        -------
            _description_
        """
        
        # For FFT, operator norm equals 1
        op_norm = torch.tensor(power_iteration(lambda x: self.op.adj(self.op.fwd(x)), x_0, niter=100))
        sigma = 1/torch.sqrt(op_norm**2 + 8)
        tau = 1/torch.sqrt(op_norm**2 + 8)
        
        print("Operator norm: ", op_norm)

        x_bar = x_0
        p = torch.zeros_like(kspace)
        q = torch.zeros_like(kspace)
                            
        for k in range(num_iterations):
            
            # Calculate p and q vectors, clip q by gamma
            p =  (p + sigma * (self.op.fwd(x_bar) - kspace)) / (1. + sigma)
            q = clip(q + sigma * self.op_dif.fwd(x_bar), torch.tensor(gamma))
            
            # Update x_1, x_bar and x_0, append result 
            x_1 = x_0 - tau * self.op.adj(p) - tau * self.op_dif.adj(q)
            
            
            if k != num_iterations - 1:
                #update xbar
                x_bar = x_1 + theta * (x_1 - x_0)
                x_0 = x_1

        return x_1
