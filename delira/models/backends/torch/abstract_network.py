import abc
import torch
from delira.models.abstract_network import AbstractNetwork

from delira.models.backends.torch.utils import scale_loss


class AbstractPyTorchNetwork(AbstractNetwork, torch.nn.Module):
    """
    Abstract Class for PyTorch Networks

    See Also
    --------
    `torch.nn.Module`
    :class:`AbstractNetwork`

    """
    @abc.abstractmethod
    def __init__(self, **kwargs):
        """

        Parameters
        ----------
        **kwargs :
            keyword arguments (are passed to :class:`AbstractNetwork`'s `
            __init__ to register them as init kwargs

        """
        torch.nn.Module.__init__(self)
        AbstractNetwork.__init__(self, **kwargs)

    @abc.abstractmethod
    def forward(self, *inputs):
        """
        Forward inputs through module (defines module behavior)
        Parameters
        ----------
        inputs : list
            inputs of arbitrary type and number

        Returns
        -------
        Any
            result: module results of arbitrary type and number

        """
        raise NotImplementedError()

    def __call__(self, *args, **kwargs):
        """
        Calls Forward method

        Parameters
        ----------
        *args :
            positional arguments (passed to `forward`)
        **kwargs :
            keyword arguments (passed to `forward`)

        Returns
        -------
        Any
            result: module results of arbitrary type and number

        """
        return torch.jit.ScriptModule.__call__(self, *args, **kwargs)

    @staticmethod
    def prepare_batch(batch: dict, input_device, output_device):
        """
        Helper Function to prepare Network Inputs and Labels (convert them
        to correct type and shape and push them to correct devices)

        Parameters
        ----------
        batch : dict
            dictionary containing all the data
        input_device : torch.device
            device for network inputs
        output_device : torch.device
            device for network outputs

        Returns
        -------
        dict
            dictionary containing data in correct type and shape and on
            correct device

        """
        return_dict = {"data": torch.from_numpy(batch["data"]).to(
            input_device).to(torch.float)}

        for key, vals in batch.items():
            if key == "data":
                continue
            return_dict[key] = torch.from_numpy(vals).to(output_device).to(
                torch.float)

        return return_dict

    @staticmethod
    def closure(model, data_dict: dict, optimizers: dict, losses: dict,
                iter_num: int, fold=0, **kwargs):
        """
        closure method to do a single backpropagation step

        Parameters
        ----------
        model : :class:`AbstractPyTorchNetwork`
            trainable model
        data_dict : dict
            dictionary containing the data
        optimizers : dict
            dictionary of optimizers to optimize model's parameters
        losses : dict
            dict holding the losses to calculate errors
            (gradients from different losses will be accumulated)
        iter_num: int
            the number of of the current iteration in the current epoch;
            Will be restarted at zero at the beginning of every epoch
        fold : int
            Current Fold in Crossvalidation (default: 0)
        **kwargs:
            additional keyword arguments

        Returns
        -------
        dict
            Loss values (with same keys as input dict losses)
        dict
            Arbitrary number of predictions as numpy array

        """

        loss_vals = {}
        total_loss = 0

        with torch.enable_grad():

            # predict
            inputs = data_dict["data"]
            preds = model(inputs)

            # calculate losses
            for key, crit_fn in losses.items():
                _loss_val = crit_fn(preds["pred"], data_dict["label"])
                loss_vals[key] = _loss_val.item()
                total_loss += _loss_val

            optimizers['default'].zero_grad()
            # perform loss scaling via apex if half precision is enabled
            with scale_loss(total_loss, optimizers["default"]) as scaled_loss:
                scaled_loss.backward()
            optimizers['default'].step()

        return loss_vals, {k: v.detach()
                           for k, v in preds.items()}
