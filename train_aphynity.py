from torch import optim
import os, sys, argparse

from experiments import APHYNITYExperiment
from networks import *
from forecasters import *
from utils import init_weights
from datasets import init_dataloaders
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

__doc__ = '''Training APHYNITY.'''

def cmdline_args():
        # Make parser object
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    
    p.add_argument("dataset", type=str,
                   help='''choose dataset: 
    'rd' - Reaction-diffusion equation
    'wave' - Wave equation
    'pendulum' - Pendulum
    ''')
    p.add_argument("-r", "--root", type=str, default='./exp',
                   help='''root path for the experiments. (default: ./exp)''')
    p.add_argument("-p", "--phy", type=str, default='incomplete',
                   help='''choose physical model type: 
    --phy incomplete - Incomplete Param PDE (default)
    --phy complete - Complete Param PDE
    --phy true - True PDE
    --phy none - No physics
    ''')
    p.add_argument("--aug", action=argparse.BooleanOptionalAction, default=True,
                   help='''enable augmentation: 
    --aug - With NN augmentaion (default)
    --no-aug - Without NN augmentation
    ''')
    p.add_argument('-d', '--device', type=str, default='cuda',
                   help='''choose device:
    'cpu' - CPU only (default)
    'cuda:X' - CUDA device.''')
    return p.parse_args()

def train_leads(dataset_name, model_phy_option, model_aug_option, path, device):
    train, test = init_dataloaders(dataset_name, os.path.join(path, dataset_name))

    if dataset_name == 'rd':
        if model_phy_option == 'incomplete':
            model_phy = ReactionDiffusionParamPDE(dx=train.dataset.dx, is_complete=False, real_params=None)
        elif model_phy_option == 'complete':
            model_phy = ReactionDiffusionParamPDE(dx=train.dataset.dx, is_complete=True, real_params=None)
        elif model_phy_option == 'true':
            model_phy = ReactionDiffusionParamPDE(dx=train.dataset.dx, is_complete=True, real_params=train.dataset.params)
        
        model_aug = ConvNetEstimator(state_c=2, hidden=16)
        net = Forecaster(model_phy=model_phy, model_aug=model_aug, is_augmented=model_aug_option)

        lambda_0 = 1.0
        tau_1 = 1e-3
        tau_2 = 1e-3
        niter = 1
        min_op = 'l2'

    if dataset_name == 'wave':
        if model_phy_option == 'incomplete':
            model_phy = DampedWaveParamPDE(is_complete=False, real_params=None)
        elif model_phy_option == 'complete':
            model_phy = DampedWaveParamPDE(is_complete=True, real_params=None)
        elif model_phy_option == 'true':
            model_phy = DampedWaveParamPDE(is_complete=True, real_params=train.dataset.params)
        
        model_aug = ConvNetEstimator(state_c=2, hidden=16)
        net = Forecaster(model_phy=model_phy, model_aug=model_aug, is_augmented=model_aug_option)

        lambda_0 = 1.0
        tau_1 = 1e-4
        tau_2 = 1e-3
        niter = 3
        min_op = 'l2'

    if dataset_name == 'pendulum':
        if model_phy_option == 'incomplete':
            model_phy = DampedPendulumParamPDE(is_complete=False, real_params=None)
        elif model_phy_option == 'complete':
            model_phy = DampedPendulumParamPDE(is_complete=True, real_params=None)
        elif model_phy_option == 'true':
            model_phy = DampedPendulumParamPDE(is_complete=True, real_params=train.dataset.params)
        
        model_aug = MLP(state_c=2, hidden=200)
        init_weights(model_aug, init_type='orthogonal', init_gain=0.2)
        net = Forecaster(model_phy=model_phy, model_aug=model_aug, is_augmented=model_aug_option)

        lambda_0 = 1.0
        tau_1 = 1e-3
        tau_2 = 1
        niter = 5
        min_op = 'l2_normalized'
    
    optimizer = optim.Adam(net.parameters(), lr=tau_1, betas=(0.9, 0.999))
    experiment = APHYNITYExperiment(
            train=train, test=test, net=net, optimizer=optimizer, 
            min_op=min_op, lambda_0=lambda_0, tau_2=tau_2, niter=niter, nlog=10,
            nupdate=100, nepoch=50000, path=path, device=device
        )
    experiment.run()

def original_main():
    if sys.version_info < (3, 7, 0):
        sys.stderr.write("You need python 3.7 or later to run this script.\n")
        sys.exit(1)
        
    args = cmdline_args()
    path = os.path.join(args.root, args.dataset)
    os.makedirs(path, exist_ok=True)
    
    option_dict = {
        'incomplete': 'Incomplete Param PDE',
        'complete': 'Complete Param PDE',
        'true': 'True PDE',
        'none': 'No physics'
    }
    print('#' * 80)
    print('#', option_dict[args.phy], 'is used in F_p')
    print('#', 'F_a is', 'enabled' if args.aug else 'disabled')
    print('#' * 80)
    train_leads(args.dataset, model_phy_option=args.phy, model_aug_option=args.aug, path=path, device=args.device)

def plot_rd():
    if sys.version_info < (3, 7, 0):
        sys.stderr.write("You need python 3.7 or later to run this script.\n")
        sys.exit(1)

    args = cmdline_args()
    path = os.path.join(args.root, args.dataset)
    os.makedirs(path, exist_ok=True)

    option_dict = {
        'incomplete': 'Incomplete Param PDE',
        'complete': 'Complete Param PDE',
        'true': 'True PDE',
        'none': 'No physics'
    }
    print('#' * 80)
    print('#', option_dict[args.phy], 'is used in F_p')
    print('#', 'F_a is', 'enabled' if args.aug else 'disabled')
    print('#' * 80)
    train, test = init_dataloaders(args.dataset, os.path.join(path, args.dataset))
    params = torch.load("./exp/rd1/model_2.997e-04.pt")
    params2 = torch.load("./exp/rd/model_4.121e-04.pt")
    model_phy = ReactionDiffusionParamPDE(dx=train.dataset.dx, is_complete=False, real_params=None)
    model_aug = ConvNetEstimator(state_c=2, hidden=16)
    net = Forecaster(model_phy=model_phy, model_aug=model_aug, is_augmented=args.aug)
    net.load_state_dict(params2["model_state_dict"])

    batch = test[0]
    for t in (9, 19, 29):
        states = batch["states"]
        y0 = states[:, :, 0]
        print(states.size())
        Utarget = states[0, 0, t].numpy()
        plt.imshow(gaussian_filter(Utarget, sigma=2), interpolation='nearest')
        plt.savefig(f"Utarget_{(t + 1) / 10}.png")
        Vtarget = states[0, 1, t].numpy()
        plt.imshow(gaussian_filter(Vtarget, sigma=2), interpolation='nearest')
        plt.savefig(f"Vtarget_{(t + 1) / 10}.png")

        pred = net(y0, batch['t'][0])
        print(pred.size())
        Upred = pred[0, 0, t].detach().numpy()
        plt.imshow(gaussian_filter(Upred, sigma=2), interpolation='nearest')
        plt.savefig(f"Upred_{(t + 1) / 10}.png")
        Vpred = pred[0, 1, t].detach().numpy()
        plt.imshow(gaussian_filter(Vpred, sigma=2), interpolation='nearest')
        plt.savefig(f"Vpred_{(t + 1) / 10}.png")

def plot_wave():
    if sys.version_info < (3, 7, 0):
        sys.stderr.write("You need python 3.7 or later to run this script.\n")
        sys.exit(1)

    args = cmdline_args()
    path = os.path.join(args.root, args.dataset)
    os.makedirs(path, exist_ok=True)

    option_dict = {
        'incomplete': 'Incomplete Param PDE',
        'complete': 'Complete Param PDE',
        'true': 'True PDE',
        'none': 'No physics'
    }
    print('#' * 80)
    print('#', option_dict[args.phy], 'is used in F_p')
    print('#', 'F_a is', 'enabled' if args.aug else 'disabled')
    print('#' * 80)
    train, test = init_dataloaders(args.dataset, os.path.join(path, args.dataset))
    params = torch.load("./exp/wave/model_9.786e-01.pt")

    model_phy = DampedWaveParamPDE(is_complete=False, real_params=None)
    model_aug = ConvNetEstimator(state_c=2, hidden=16)
    net = Forecaster(model_phy=model_phy, model_aug=model_aug, is_augmented=args.aug)
    net.load_state_dict(params["model_state_dict"])
    for j, batch in enumerate(test):
        states = batch["states"]
        y0 = states[:, :, 0]
        print(states.size())
        i = 1
        for t in (4, 14, 24):
            w_target = states[i, 0, t].numpy()
            # ax = plt.gca()
            # ax.set_xlim([0, 35])
            # ax.set_ylim([0, 35])
            plt.imshow(gaussian_filter(w_target, sigma=0), interpolation='nearest')
            plt.savefig(f"figures/wave/1/w_target_{t+1}.png")
            dwdt_target = states[i, 1, t].numpy()
            plt.imshow(gaussian_filter(dwdt_target, sigma=0), interpolation='nearest')
            plt.savefig(f"figures/wave/1/dwdt_target_{t+1}.png")

            pred = net(y0, batch['t'][0])

            w_pred = pred[i, 0, t].detach().numpy()
            plt.imshow(gaussian_filter(w_pred, sigma=0), interpolation='nearest')
            plt.savefig(f"figures/wave/1/w_pred_{t+1}.png")
            dwdt_pred = pred[i, 1, t].detach().numpy()
            plt.imshow(gaussian_filter(dwdt_pred, sigma=0), interpolation='nearest')
            plt.savefig(f"figures/wave/1/dwdt_pred_{t+1}.png")
        break

    # batch = test[0]
    # for t in (9, 19, 29):
    #     states = batch["states"]
    #     y0 = states[:, :, 0]
    #     print(states.size())
        # Utarget = states[0, 0, t].numpy()
        # plt.imshow(gaussian_filter(Utarget, sigma=2), interpolation='nearest')
        # plt.savefig(f"Utarget_{(t + 1) / 10}.png")
        # Vtarget = states[0, 1, t].numpy()
        # plt.imshow(gaussian_filter(Vtarget, sigma=2), interpolation='nearest')
        # plt.savefig(f"Vtarget_{(t + 1) / 10}.png")
        #
        # pred = net(y0, batch['t'][0])
        # print(pred.size())
        # Upred = pred[0, 0, t].detach().numpy()
        # plt.imshow(gaussian_filter(Upred, sigma=2), interpolation='nearest')
        # plt.savefig(f"Upred_{(t + 1) / 10}.png")
        # Vpred = pred[0, 1, t].detach().numpy()
        # plt.imshow(gaussian_filter(Vpred, sigma=2), interpolation='nearest')
        # plt.savefig(f"Vpred_{(t + 1) / 10}.png")

def plot_pendulum():
    pass

if __name__ == '__main__':
    original_main()
    #plot_wave()
