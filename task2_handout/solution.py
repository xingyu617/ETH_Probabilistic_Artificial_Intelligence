import os
import typing

import numpy as np
import torch
import torch.optim
from matplotlib import pyplot as plt
from sklearn.metrics import roc_auc_score, average_precision_score
from torch import nn
from torch.nn import functional as F
from tqdm import trange
from torch.autograd import Variable
from torchvision import models, transforms, datasets
import math
#from skimage.transform import rotate
#from skimage.util import random_noise
#from skimage.filters import gaussian
from util import ece, ParameterDistribution
torch.manual_seed(2)
#from tqdm import tqdm
torch.cuda.is_available()
# Set `EXTENDED_EVALUATION` to `True` in order to visualize your predictions.
EXTENDED_EVALUATION = False
PI = 0.75
#SIGMA_1 = torch.cuda.FloatTensor([math.exp(-0)])
#SIGMA_2 = torch.cuda.FloatTensor([math.exp(-6)])
#SIGMA_1=torch.FloatTensor([math.exp(-0)])
#SIGMA_2=torch.FloatTensor([math.exp(-6)])
SIGMA_1=torch.FloatTensor([0.135])
SIGMA_2=torch.FloatTensor([0.0001])
SAMPLES=2
CLASSES = 10
BATCH_SIZE=100
def run_solution(dataset_train: torch.utils.data.Dataset, data_dir: str = os.curdir, output_dir: str = '/results/') -> 'Model':
    """
    Run your task 2 solution.
    This method should train your model, evaluate it, and return the trained model at the end.
    Make sure to preserve the method signature and to return your trained model,
    else the checker will fail!

    :param dataset_train: Training dataset
    :param data_dir: Directory containing the datasets
    :return: Your trained model
    """

    # Create model
    model = Model()
    """
    train_tfms = transforms.Compose([
        transforms.RandomResizedCrop(224),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor()
        # don't use transforms.Normalize() for the first time
    ])
    dataset_train = datasets.ImageFolder(root=data_dir, transform=train_tfms)
    """
    # Train the model
    print('Training model')
    model.train(dataset_train)

    # Predict using the trained model
    print('Evaluating model on training data')
    eval_loader = torch.utils.data.DataLoader(
        dataset_train, batch_size=64, shuffle=False, drop_last=False
    )
    evaluate(model, eval_loader, data_dir, output_dir)

    # IMPORTANT: return your model here!
    return model


class Model(object):
    """
    Task 2 model that can be used to train a BNN using Bayes by backprop and create predictions.
    You need to implement all methods of this class without changing their signature,
    else the checker will fail!
    """

    def __init__(self):
        # Hyperparameters and general parameters
        # You might want to play around with those
        self.num_epochs = 100  # number of training epochs
        self.batch_size = 128  # training batch size
        learning_rate = 1e-5  # training learning rates
        # hidden_layers = (128, 128)  # for each entry, creates a hidden layer with the corresponding number of units
        hidden_layers = (128,128,128)  # for each entry, creates a hidden layer with the corresponding number of units
        use_densenet = False  # set this to True in order to run a DenseNet for comparison
        self.print_interval = 100  # number of batches until updated metrics are displayed during training

        # Determine network typeafs
        if use_densenet:
            # DenseNet
            print('Using a DenseNet model for comparison')
            self.network = DenseNet(in_features=28 * 28, hidden_features=hidden_layers, out_features=10)
        else:
            # BayesNet
            print('Using a BayesNet model')
            self.network = BayesNet(in_features=28 * 28, hidden_features=hidden_layers, out_features=10)

        # Optimizer for training
        # Feel free to try out different optimizers
        # self.optimizer = torch.optim.Adam(self.network.parameters(), lr=learning_rate)
        self.optimizer = torch.optim.SGD(self.network.parameters(), lr=learning_rate,momentum=0.85)

    def train(self, dataset: torch.utils.data.Dataset):
        """
        Train your neural network.
        If the network is a DenseNet, this performs normal stochastic gradient descent training.
        If the network is a BayesNet, this should perform Bayes by backprop.

        :param dataset: Dataset you should use for training
        """

        Nbatches = len(dataset)/self.batch_size
        train_loader = torch.utils.data.DataLoader(
            dataset, batch_size=self.batch_size, shuffle=True, drop_last=True
        )

        self.network.train()

        progress_bar = trange(self.num_epochs)
        for _ in progress_bar:
            num_batches = len(train_loader)
            for batch_idx, (batch_x, batch_y) in enumerate(train_loader):
                # batch_x are of shape (batch_size, 784), batch_y are of shape (batch_size,)
                # print(batch_x.shape)
                self.network.zero_grad()

                if isinstance(self.network, DenseNet):
                    # DenseNet training step

                    # Perform forward pass
                    current_logits = self.network(batch_x)

                    # Calculate the loss
                    # We use the negative log likelihood as the loss
                    # Combining nll_loss with a log_softmax is better for numeric stability
                    loss = F.nll_loss(F.log_softmax(current_logits, dim=1), batch_y, reduction='sum')

                    # Backpropagate to get the gradients
                    loss.backward()
                else:
                    # BayesNet training step via Bayes by backprop
                    assert isinstance(self.network, BayesNet)
                    
                    
                    # self.optimizer.step()
                    
                    

                    # TODO: Implement Bayes by backprop training heredocker build --tag task2 .
                    # print(batch_x.shape)
                    #batch_x, batch_y = batch_x.to(DEVICE), batch_y.to(DEVICE)
                    self.network.zero_grad()
                    out, tlqw, tlpw = self.network(batch_x)
                    #mlpdw = F.cross_entropy(out, batch_y, reduction='sum')
                    mlpdw=F.nll_loss(F.log_softmax(out), batch_y, size_average=False)
                    #mlpdw = F.nll_loss(F.log_softmax((out,dim=1)), batch_y, reduction='sum')
                    Edkl = (tlqw - tlpw) / Nbatches
                    #loss = self.network.sample_elbo(batch_x,batch_y,batch_size=self.batch_size,num_batches=Nbatches)
                    loss = Edkl + mlpdw

                    ##loss, log_prior, log_variational_posterior, negative_log_likelihood = self.network.sample_elbo(batch_x, batch_y,self.batch_size,Nbatches)
                    #print(loss)

                    loss.backward()


                self.optimizer.step()

                # Update progress bar with accuracy occasionally
                if batch_idx % self.print_interval == 0:
                    if isinstance(self.network, DenseNet):
                        current_logits = self.network(batch_x)
                    else:
                        assert isinstance(self.network, BayesNet)
                        current_logits, _, _ = self.network(batch_x)
                    current_accuracy = (current_logits.argmax(axis=1) == batch_y).float().mean()
                    progress_bar.set_postfix(loss=loss.item(), acc=current_accuracy.item())

    def predict(self, data_loader: torch.utils.data.DataLoader) -> np.ndarray:
        """
        Predict the class probabilities using your trained model.
        This method should return an (num_samples, 10) NumPy float array
        such that the second dimension sums up to 1 for each row.

        :param data_loader: Data loader yielding the samples to predict on
        :return: (num_samples, 10) NumPy float array where the second dimension sums up to 1 for each row
        """

        self.network.eval()

        probability_batches = []
        for batch_x, batch_y in data_loader:
            current_probabilities = self.network.predict_probabilities(batch_x).detach().numpy()
            probability_batches.append(current_probabilities)

        output = np.concatenate(probability_batches, axis=0)
        assert isinstance(output, np.ndarray)
        assert output.ndim == 2 and output.shape[1] == 10
        assert np.allclose(np.sum(output, axis=1), 1.0)
        return output

#test dropout by XC
def MC_dropout(act_vec, p=0.5, mask=True):
    return F.dropout(act_vec, p=p, training=mask, inplace=True)

class BayesianLayer(nn.Module):
    """
    Module implementing a single Bayesian feedforward layer.
    It maintains a prior and variational posterior for the weights (and biases)
    and uses sampling to approximate the gradients via Bayes by backprop.
    """
    def __init__(self, in_features: int, out_features: int, bias: bool = True):
        """
        Create a BayesianLayer.

        :param in_features: Number of input features
        :param out_features: Number of output features
        :param bias: If true, use a bias term (i.e., affine instead of linear transformation)
        """
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.use_bias = bias

        # TODO: Create a suitable prior for weights and biases as an instance of ParameterDistribution.
        #  You can use the same prior for both weights and biases, but are free to experiment with different priors.
        #  You can create constants using torch.tensor(...).
        #  Do NOT use torch.Parameter(...) here since the prior should not be optimized!
        #  Example: self.prior = MyPrior(torch.tensor(0.0), torch.tensor(1.0))
        # self.prior = None
        
        # self.prior = isotropic_gauss_prior(mu=0, sigma=0.1)
        # self.prior = spike_slab_2GMM(mu1=0, mu2=0, sigma1=0.1, sigma2=0.0005, pi=0.75)
        #self.prior = spike_slab_2GMM(mu1=0, mu2=0, sigma1=0.135, sigma2=0.001, pi=0.5)
        #self.prior=ScaleMixtureGaussian(PI, SIGMA_1, SIGMA_2)
        # Learnable parameters
        # Weight parameters
        self.weight_mu = nn.Parameter(torch.Tensor(out_features, in_features).uniform_(-0.1, 0.1))
        self.weight_rho = nn.Parameter(torch.Tensor(out_features, in_features).uniform_(-3,-1))
        self.weights_var_posterior = Gaussian(self.weight_mu, self.weight_rho)

        # Prior distributions
        self.weight_prior = ScaleMixtureGaussian(PI, SIGMA_1, SIGMA_2)

        self.log_prior = 0
        self.log_variational_posterior = 0

        
        
        
        # assert isinstance(self.prior, ParameterDistribution)
        # assert not any(True for _ in self.prior.parameters()), 'Prior cannot have parameters'

        # TODO: Create a suitable variational posterior for weights as an instance of ParameterDistribution.
        #  You need to create separate ParameterDistribution instances for weights and biases,
        #  but can use the same family of distributions if you want.
        #  IMPORTANT: You need to create a nn.Parameter(...) for each parameter
        #  and add those parameters as an attribute in the ParameterDistribution instances.
        #  If you forget to do so, PyTorch will not be able to optimize your variational posterior.
        #  Example: self.weights_var_posterior = MyPosterior(
        #      torch.nn.Parameter(torch.zeros((out_features, in_features))),
        #      torch.nn.Parameter(torch.ones((out_features, in_features)))
        #  )


        # assert isinstance(self.weights_var_posterior, ParameterDistribution)
        # assert any(True for _ in self.weights_var_posterior.parameters()), 'Weight posterior must have parameters'

        if self.use_bias:
            # TODO: As for the weights, create the bias variational posterior instance here.
            #  Make sure to follow the same rules as for the weight variational posterior.
            # self.bias_var_posterior = None
            # Bias parameters
            self.bias_mu = nn.Parameter(torch.Tensor(out_features).uniform_(-0.1, 0.1))
            self.bias_rho = nn.Parameter(torch.Tensor(out_features).uniform_(-3,-1))
            self.bias_var_posterior = Gaussian(self.bias_mu, self.bias_rho)
            self.bias_prior = ScaleMixtureGaussian(PI, SIGMA_1, SIGMA_2)
            # assert isinstance(self.bias_var_posterior, ParameterDistribution)
            # assert any(True for _ in self.bias_var_posterior.parameters()), 'Bias posterior must have parameters'
        else:
            self.bias_var_posterior = None
            self.bias_prior=None

    def forward(self, inputs: torch.Tensor):
        """
        Perform one forward pass through this layer.
        If you need to sample weights from the variational posterior, you can do it here during the forward pass.
        Just make sure that you use the same weights to approximate all quantities
        present in a single Bayes by backprop sampling step.

        :param inputs: Flattened input images as a (batch_size, in_features) float tensor
        :return: 3-tuple containing
            i) transformed features using stochastic weights from the variational posterior,
            ii) sample of the log-prior probability, and
            iii) sample of the log-variational-posterior probability
        """
        # TODO: Perform a forward pass as described in this method's docstring.
        #  Make sure to check whether `self.use_bias` is True,
        #  and if yes, include the bias as well.
        weight = self.weights_var_posterior.mu

        if self.use_bias:
            bias = self.bias_var_posterior.mu
            self.log_prior = self.weight_prior.log_prob(weight) + self.bias_prior.log_prob(bias)
            self.log_variational_posterior = self.weights_var_posterior.log_prob(weight) + self.bias_var_posterior.log_prob(bias)
        else:
            self.log_prior = self.weight_prior.log_prob(weight)
            self.log_variational_posterior = self.weights_var_posterior.log_prob(weight)
            
        
        log_prior = self.log_prior
    
        log_variational_posterior = self.log_variational_posterior
        return F.linear(inputs, weight, bias), log_prior, log_variational_posterior


class BayesNet(nn.Module):
    """
    Module implementing a Bayesian feedforward neural network using BayesianLayer objects.
    """

    def __init__(self, in_features: int, hidden_features: typing.Tuple[int, ...], out_features: int):
        """
        Create a BNN.

        :param in_features: Number of input features
        :param hidden_features: Tuple where each entry corresponds to a (Bayesian) hidden layer with
            the corresponding number of features.
        :param out_features: Number of output features
        """

        super().__init__()
        print(in_features,hidden_features,out_features)
        feature_sizes = (in_features,) + hidden_features + (out_features,)
        num_affine_maps = len(feature_sizes) - 1
        self.layers = nn.ModuleList([
            BayesianLayer(feature_sizes[idx], feature_sizes[idx + 1], bias=True)
            for idx in range(num_affine_maps)
        ])
        self.activation = nn.ReLU()
        # self.activation = nn.SELU()
        self.in_features = in_features
        self.pdrop = 0.5

    def forward(self, x: torch.Tensor) -> typing.Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Perform one forward pass through the BNN using a single set of weights
        sampled from the variational posterior.

        :param x: Input features, float tensor of shape (batch_size, in_features)
        :return: 3-tuple containing
            i) output features using stochastic weights from the variational posterior,
            ii) sample of the log-prior probability, and
            iii) sample of the log-variational-posterior probability
        """

        # TODO: Perform a full pass through your BayesNet as described in this method's docstring.
        #  You can look at DenseNet to get an idea how a forward pass might look like.
        #  Don't forget to apply your activation function in between BayesianLayers!
        
        
            
        
        mask=True
        log_prior = torch.tensor(0.0)
        log_variational_posterior = torch.tensor(0.0)

        tlqw = 0
        tlpw = 0
        current_features = x.view(-1, self.in_features)
        for idx, current_layer in enumerate(self.layers):
            new_features, lqw, lpw = current_layer(current_features)

            if idx < len(self.layers)-1:
                new_features = MC_dropout(new_features, p=self.pdrop, mask=mask)
                new_features = self.activation(new_features)

                tlqw += lqw
                tlpw += lpw
                # current_features=self.activation(new_features)
            elif idx==len(self.layers):
                new_features=F.log_softmax(new_features,dim=1)
                tlqw += lqw
                tlpw += lpw

            current_features = new_features
            log_prior = tlpw
            log_variational_posterior = tlqw

        return current_features, log_prior, log_variational_posterior


    def predict_probabilities(self, x: torch.Tensor, num_mc_samples: int = 10) -> torch.Tensor:
        """
        Predict class probabilities for the given features by sampling from this BNN.

        :param x: Features to predict on, float tensor of shape (batch_size, in_features)
        :param num_mc_samples: Number of MC samples to take for prediction
        :return: Predicted class probabilities, float tensor of shape (batch_size, 10)
            such that the last dimension sums up to 1 for each row
        """
        probability_samples = torch.stack([F.softmax(self.forward(x)[0], dim=1) for _ in range(num_mc_samples)], dim=0)
        estimated_probability = torch.mean(probability_samples, dim=0)

        assert estimated_probability.shape == (x.shape[0], 10)
        assert torch.allclose(torch.sum(estimated_probability, dim=1), torch.tensor(1.0))
        return estimated_probability

    def sample_elbo(self, input, target, batch_size,num_batches,samples=SAMPLES):
        outputs = torch.zeros(samples, batch_size, CLASSES)
        log_priors = torch.zeros(samples)
        log_variational_posteriors = torch.zeros(samples)
        for i in range(samples):
            outputs[i],log_priors[i],log_variational_posteriors[i]= self.forward(input)

        log_prior = log_priors.mean()
        log_variational_posterior = log_variational_posteriors.mean()
        negative_log_likelihood = F.nll_loss(outputs.mean(0), target, size_average=False)
        loss = (log_variational_posterior - log_prior) / num_batches + negative_log_likelihood
        if(loss==-math.inf):
            print(log_variational_posterior,log_prior,num_batches,negative_log_likelihood)
        return loss, log_prior, log_variational_posterior, negative_log_likelihood


class Gaussian(object):
    def __init__(self, mu, rho):
        super().__init__()
        self.mu = mu
        self.rho = rho
        self.normal = torch.distributions.Normal(0, 1)

    @property
    def sigma(self):
        return torch.log1p(torch.exp(self.rho))

    def sample(self):
        epsilon = self.normal.sample(self.rho.size()).to(DEVICE)
        return self.mu + self.sigma * epsilon

    def log_prob(self, input):
        return (-math.log(math.sqrt(2 * math.pi))
                - torch.log(self.sigma)
                - ((input - self.mu) ** 2) / (2 * self.sigma ** 2)).sum()
class ScaleMixtureGaussian(object):
    def __init__(self, pi, sigma1, sigma2):
        super().__init__()
        self.pi = pi
        self.sigma1 = sigma1
        self.sigma2 = sigma2
        self.gaussian1 = torch.distributions.Normal(0, sigma1)
        self.gaussian2 = torch.distributions.Normal(0, sigma2)

    def log_prob(self, input):
        #print(len(input))
        prob1 = torch.exp(self.gaussian1.log_prob(input))
        prob2 = torch.exp(self.gaussian2.log_prob(input))
        return (torch.log(self.pi * prob1 + (1 - self.pi) * prob2)).sum()

class UnivariateGaussian(ParameterDistribution):
    """
    Univariate Gaussian distribution.
    For multivariate data, this assumes all elements to be i.i.d.
    """

    def __init__(self, mu: torch.Tensor, sigma: torch.Tensor):
        super(UnivariateGaussian, self).__init__()  # always make sure to include the super-class init call!
        assert mu.size() == () and sigma.size() == ()
        assert sigma > 0
        self.mu = mu
        self.sigma = sigma
        self.normal = torch.distributions.Normal(0, 1)

    def log_likelihood(self, values: torch.Tensor) -> torch.Tensor:
        # TODO: Implement this
        return (-math.log(math.sqrt(2 * math.pi))
                - torch.log(self.sigma)
                - ((input - self.mu) ** 2) / (2 * self.sigma ** 2)).sum()

    def sample(self) -> torch.Tensor:
        # TODO: Implement this
        epsilon = self.normal.sample(self.sigma.size())
        return self.mu + self.sigma * epsilon
        #raise NotImplementedError()

class MultivariateDiagonalGaussian(ParameterDistribution):
    """
    Multivariate diagonal Gaussian distribution,
    i.e., assumes all elements to be independent Gaussians
    but with different means and standard deviations.
    This parameterizes the standard deviation via a parameter rho as
    sigma = softplus(rho).
    """

    def __init__(self, mu: torch.Tensor, rho: torch.Tensor):
        super(MultivariateDiagonalGaussian, self).__init__()  # always make sure to include the super-class init call!
        assert mu.size() == rho.size()
        self.mu = mu
        self.rho = rho
        self.normal = torch.distributions.Normal(0, 1)

    #def sigma(self):
        #return torch.log1p(torch.exp(self.rho))

    def log_likelihood(self, values: torch.Tensor) -> torch.Tensor:
        # TODO: Implement this
        sigma=torch.log1p(torch.exp(self.rho))
        return (-math.log(math.sqrt(2 * math.pi))
                - torch.log(sigma)
                - ((input - self.mu) ** 2) / (2 * sigma ** 2)).sum()

    def sample(self) -> torch.Tensor:
        # TODO: Implement this
        epsilon = self.normal.sample(self.rho.size())
        return self.mu + sigma * epsilon
        #raise NotImplementedError()

def evaluate(model: Model, eval_loader: torch.utils.data.DataLoader, data_dir: str, output_dir: str):
    """
    Evaluate your model.
    :param model: Trained model to evaluate
    :param eval_loader: Data loader containing the training set for evaluation
    :param data_dir: Data directory from which additional datasets are loaded
    :param output_dir: Directory into which plots are saved
    """

    # Predict class probabilities on test data
    predicted_probabilities = model.predict(eval_loader)

    # Calculate evaluation metrics
    predicted_classes = np.argmax(predicted_probabilities, axis=1)
    actual_classes = eval_loader.dataset.tensors[1].detach().numpy()
    accuracy = np.mean((predicted_classes == actual_classes))
    ece_score = ece(predicted_probabilities, actual_classes)
    print(f'Accuracy: {accuracy.item():.3f}, ECE score: {ece_score:.3f}')

    if EXTENDED_EVALUATION:
        eval_samples = eval_loader.dataset.tensors[0].detach().numpy()

        # Determine confidence per sample and sort accordingly
        confidences = np.max(predicted_probabilities, axis=1)
        sorted_confidence_indices = np.argsort(confidences)

        # Plot samples your model is most confident about
        print('Plotting most confident MNIST predictions')
        most_confident_indices = sorted_confidence_indices[-10:]
        fig, ax = plt.subplots(4, 5, figsize=(13, 11))
        for row in range(0, 4, 2):
            for col in range(5):
                sample_idx = most_confident_indices[5 * row // 2 + col]
                ax[row, col].imshow(np.reshape(eval_samples[sample_idx], (28, 28)), cmap='gray')
                ax[row, col].set_axis_off()
                ax[row + 1, col].set_title(f'predicted {predicted_classes[sample_idx]}, actual {actual_classes[sample_idx]}')
                bar_colors = ['C0'] * 10
                bar_colors[actual_classes[sample_idx]] = 'C1'
                ax[row + 1, col].bar(
                    np.arange(10), predicted_probabilities[sample_idx], tick_label=np.arange(10), color=bar_colors
                )
        fig.suptitle('Most confident predictions', size=20)
        fig.savefig(os.path.join(output_dir, 'mnist_most_confident.pdf'))

        # Plot samples your model is least confident about
        print('Plotting least confident MNIST predictions')
        least_confident_indices = sorted_confidence_indices[:10]
        fig, ax = plt.subplots(4, 5, figsize=(13, 11))
        for row in range(0, 4, 2):
            for col in range(5):
                sample_idx = least_confident_indices[5 * row // 2 + col]
                ax[row, col].imshow(np.reshape(eval_samples[sample_idx], (28, 28)), cmap='gray')
                ax[row, col].set_axis_off()
                ax[row + 1, col].set_title(f'predicted {predicted_classes[sample_idx]}, actual {actual_classes[sample_idx]}')
                bar_colors = ['C0'] * 10
                bar_colors[actual_classes[sample_idx]] = 'C1'
                ax[row + 1, col].bar(
                    np.arange(10), predicted_probabilities[sample_idx], tick_label=np.arange(10), color=bar_colors
                )
        fig.suptitle('Least confident predictions', size=20)
        fig.savefig(os.path.join(output_dir, 'mnist_least_confident.pdf'))

        print('Plotting ambiguous and rotated MNIST confidences')
        ambiguous_samples = torch.from_numpy(np.load(os.path.join(data_dir, 'test_x.npz'))['test_x']).reshape([-1, 784])[:10]
        ambiguous_dataset = torch.utils.data.TensorDataset(ambiguous_samples, torch.zeros(10))
        ambiguous_loader = torch.utils.data.DataLoader(
            ambiguous_dataset, batch_size=10, shuffle=False, drop_last=False
        )
        ambiguous_predicted_probabilities = model.predict(ambiguous_loader)
        ambiguous_predicted_classes = np.argmax(ambiguous_predicted_probabilities, axis=1)
        fig, ax = plt.subplots(4, 5, figsize=(13, 11))
        for row in range(0, 4, 2):
            for col in range(5):
                sample_idx = 5 * row // 2 + col
                ax[row, col].imshow(np.reshape(ambiguous_samples[sample_idx], (28, 28)), cmap='gray')
                ax[row, col].set_axis_off()
                ax[row + 1, col].set_title(f'predicted {ambiguous_predicted_classes[sample_idx]}')
                ax[row + 1, col].bar(
                    np.arange(10), ambiguous_predicted_probabilities[sample_idx], tick_label=np.arange(10)
                )
        fig.suptitle('Predictions on ambiguous and rotated MNIST', size=20)
        fig.savefig(os.path.join(output_dir, 'ambiguous_rotated_mnist.pdf'))

        # Do the same evaluation as on MNIST also on FashionMNIST
        print('Predicting on FashionMNIST data')
        fmnist_samples = torch.from_numpy(np.load(os.path.join(data_dir, 'fmnist.npz'))['x_test']).reshape([-1, 784])
        fmnist_dataset = torch.utils.data.TensorDataset(fmnist_samples, torch.zeros(fmnist_samples.shape[0]))
        fmnist_loader = torch.utils.data.DataLoader(
            fmnist_dataset, batch_size=64, shuffle=False, drop_last=False
        )
        fmnist_predicted_probabilities = model.predict(fmnist_loader)
        fmnist_predicted_classes = np.argmax(fmnist_predicted_probabilities, axis=1)
        fmnist_confidences = np.max(fmnist_predicted_probabilities, axis=1)
        fmnist_sorted_confidence_indices = np.argsort(fmnist_confidences)

        # Plot FashionMNIST samples your model is most confident about
        print('Plotting most confident FashionMNIST predictions')
        most_confident_indices = fmnist_sorted_confidence_indices[-10:]
        fig, ax = plt.subplots(4, 5, figsize=(13, 11))
        for row in range(0, 4, 2):
            for col in range(5):
                sample_idx = most_confident_indices[5 * row // 2 + col]
                ax[row, col].imshow(np.reshape(fmnist_samples[sample_idx], (28, 28)), cmap='gray')
                ax[row, col].set_axis_off()
                ax[row + 1, col].set_title(f'predicted {fmnist_predicted_classes[sample_idx]}')
                ax[row + 1, col].bar(
                    np.arange(10), fmnist_predicted_probabilities[sample_idx], tick_label=np.arange(10)
                )
        fig.suptitle('Most confident predictions', size=20)
        fig.savefig(os.path.join(output_dir, 'fashionmnist_most_confident.pdf'))

        # Plot FashionMNIST samples your model is least confident about
        print('Plotting least confident FashionMNIST predictions')
        least_confident_indices = fmnist_sorted_confidence_indices[:10]
        fig, ax = plt.subplots(4, 5, figsize=(13, 11))
        for row in range(0, 4, 2):
            for col in range(5):
                sample_idx = least_confident_indices[5 * row // 2 + col]
                ax[row, col].imshow(np.reshape(fmnist_samples[sample_idx], (28, 28)), cmap='gray')
                ax[row, col].set_axis_off()
                ax[row + 1, col].set_title(f'predicted {fmnist_predicted_classes[sample_idx]}')
                ax[row + 1, col].bar(
                    np.arange(10), fmnist_predicted_probabilities[sample_idx], tick_label=np.arange(10)
                )
        fig.suptitle('Least confident predictions', size=20)
        fig.savefig(os.path.join(output_dir, 'fashionmnist_least_confident.pdf'))

        print('Determining suitability of your model for OOD detection')
        all_confidences = np.concatenate([confidences, fmnist_confidences])
        dataset_labels = np.concatenate([np.ones_like(confidences), np.zeros_like(fmnist_confidences)])
        print(
            'AUROC for MNIST vs. FashionMNIST OOD detection based on confidence: '
            f'{roc_auc_score(dataset_labels, all_confidences):.3f}'
        )
        print(
            'AUPRC for MNIST vs. FashionMNIST OOD detection based on confidence: '
            f'{average_precision_score(dataset_labels, all_confidences):.3f}'
        )


class DenseNet(nn.Module):
    """
    Simple module implementing a feedforward neural network.
    You can use this model as a reference/baseline for calibration
    in the normal neural network case.
    """

    def __init__(self, in_features: int, hidden_features: typing.Tuple[int, ...], out_features: int):
        """
        Create a normal NN.

        :param in_features: Number of input features
        :param hidden_features: Tuple where each entry corresponds to a hidden layer with
            the corresponding number of features.
        :param out_features: Number of output features
        """
        super().__init__()

        feature_sizes = (in_features,) + hidden_features + (out_features,)
        num_affine_maps = len(feature_sizes) - 1
        self.layers = nn.ModuleList([
            nn.Linear(feature_sizes[idx], feature_sizes[idx + 1], bias=True)
            for idx in range(num_affine_maps)
        ])
        self.activation = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        current_features = x

        for idx, current_layer in enumerate(self.layers):
            new_features = current_layer(current_features)
            if idx < len(self.layers) - 1:
                new_features = self.activation(new_features)
            current_features = new_features

        return current_features

    def predict_probabilities(self, x: torch.Tensor) -> torch.Tensor:
        assert x.shape[1] == 28 ** 2
        estimated_probability = F.softmax(self.forward(x), dim=1)
        assert estimated_probability.shape == (x.shape[0], 10)
        return estimated_probability


def main():
    """
    raise RuntimeError(
        'This main method is for illustrative purposes only and will NEVER be called by the checker!\n'
        'The checker always calls run_solution directly.\n'
        'Please implement your solution exclusively in the methods and classes mentioned in the task description.'
    )
    """

    # Load training data
    data_dir = os.curdir
    output_dir = os.curdir
    raw_train_data = np.load(os.path.join(data_dir, 'train_data.npz'))
    x_train = torch.from_numpy(raw_train_data['train_x']).reshape([-1, 784])
    #print(x_train.shape)
    y_train = torch.from_numpy(raw_train_data['train_y']).long()
    #print(y_train.shape)
    """
    x_train = torch.from_numpy(raw_train_data['train_x'])
    y_train = torch.from_numpy(raw_train_data['train_y'])
    #dataset_train = torch.utils.data.TensorDataset(x_train, y_train)
    print(x_train.shape)
    #try data sugumentation
    #final_train_data = np.empty((x_train.shape[0],5))
    #final_target_train = np.empty((x_train.shape[0],5))
    final_train_data=[]
    final_target_train=[]
    for i in tqdm(range(x_train.shape[0])):
        final_train_data.append(x_train[i])
        final_train_data.append(rotate(x_train[i], angle=45, mode='wrap'))
        final_train_data.append(np.fliplr(x_train[i]))
        final_train_data.append(np.flipud(x_train[i]))
        final_train_data.append(random_noise(x_train[i], var=0.2 ** 2))
        for j in range(5):
            final_target_train.append(y_train[i])
    print(x_train.shape)

    #print(len(final_target_train), len(final_train_data))
    final_target_train = np.array(final_target_train)
    final_train_data = np.array(final_train_data)
    print("final train data: ",final_train_data[1],final_train_data[1].reshape(-1,784).shape)
    print("final train data shape: ",final_train_data.shape,final_train_data[1].shape)

    print(final_target_train[1])
    print(final_target_train.shape)

    final_train =np.empty((300000,784))
    for i in range(final_train.shape[0]):
        final_train[i]=final_train_data[i].reshape(-1,784)
    print("final train data shape: ", final_train.shape, final_train[1].shape)
    final_target_train = np.array(final_target_train)
    print(final_target_train.shape, final_train.shape)
    final_train=torch.from_numpy(final_train)
    final_target_train=torch.from_numpy(final_target_train)
    """
    # Run actual solution
    dataset_train = torch.utils.data.TensorDataset(x_train, y_train)
    run_solution(dataset_train, data_dir=data_dir, output_dir=output_dir)


if __name__ == "__main__":
    main()
