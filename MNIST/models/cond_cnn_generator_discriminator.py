'''

based on the CNN structure in "Spectral normalization for generator adversarial networks"

'''
import torch
import torch.nn as nn
import numpy as np

default_bias = True
#########################################################
# genearator
class cond_cnn_generator(nn.Module):
    def __init__(self, ngpu=2, nz=128, ngf=64, nc=1, bias = default_bias):
        super(cond_cnn_generator, self).__init__()
        self.nz = nz
        self.ngpu = ngpu
        self.ngf =ngf
        self.linear = nn.Linear(nz+1, 7 * 7 * ngf * 4) #7*7*256
        self.main = nn.Sequential(
            # state size. (ngf*4) x 7 x 7
            nn.ConvTranspose2d(ngf * 4, ngf * 2, kernel_size=4, stride=2, padding=1, bias=bias), #h=2h
            nn.BatchNorm2d(ngf * 2),
            nn.ReLU(True),
            # state size. (ngf*2) x 14 x 14
            nn.ConvTranspose2d(ngf * 2, ngf, kernel_size=4, stride=2, padding=1, bias=bias), #h=2h
            nn.BatchNorm2d(ngf),
            nn.ReLU(True),
            # state size. ngf x 28 x 28
            nn.Conv2d(ngf, nc, kernel_size=3, stride=1, padding=1, bias=bias), #h=h
            nn.Tanh()
            # state size. (nc) x 32 x 32
        )

    def forward(self, input, labels):
        input = input.view(-1, self.nz)
        labels = labels.view(-1, 1)
        input = torch.cat((labels, input), 1)
        if input.is_cuda and self.ngpu > 1:
            output = nn.parallel.data_parallel(self.linear, input, range(self.ngpu))
            output = output.view(-1, 4*self.ngf, 7, 7)
            output = nn.parallel.data_parallel(self.main, output, range(self.ngpu))
        else:
            output = self.linear(input)
            output = output.view(-1, 4*self.ngf, 7, 7)
            output = self.main(output)
        return output

#########################################################
# discriminator
class cond_cnn_discriminator(nn.Module):
    def __init__(self, use_sigmoid = True, ngpu=2, nc=1, ndf=64, bias = default_bias):
        super(cond_cnn_discriminator, self).__init__()
        self.ngpu = ngpu
        self.ndf = ndf
        self.main = nn.Sequential(
            # input is (nc) x 28 x 28
            nn.Conv2d(nc, ndf, kernel_size=3, stride=1, padding=1, bias=bias), #h=h
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(ndf, ndf, kernel_size=4, stride=2, padding=1, bias=bias), #h=h/2
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf) x 14 x 14
            nn.Conv2d(ndf, ndf*2, kernel_size=3, stride=1, padding=1, bias=bias), #h=h
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(ndf*2, ndf*2, kernel_size=4, stride=2, padding=1, bias=bias), #h=h/2
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*2) x 7 x 7
            nn.Conv2d(ndf*2, ndf*4, kernel_size=3, stride=1, padding=1, bias=bias), #h=h
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*4) x 7 x 7
        )
        linear = [nn.Linear(ndf*4*7*7+1, 512),
                  nn.BatchNorm1d(512),
                  nn.ReLU(),
                  nn.Linear(512,1)]
        if use_sigmoid:
            linear += [nn.Sigmoid()]
        self.linear = nn.Sequential(*linear)

    def forward(self, input, labels):
        labels = labels.view(-1,1)
        if input.is_cuda and self.ngpu > 1:
            output = nn.parallel.data_parallel(self.main, input, range(self.ngpu))
            output = output.view(-1, self.ndf*4*7*7)
            output = torch.cat((labels, output), 1)
            output = nn.parallel.data_parallel(self.linear, output, range(self.ngpu))
        else:
            output = self.main(input)
            output = output.view(-1, self.ndf*4*7*7)
            output = torch.cat((labels, output), 1)
            output = self.linear(output)

        return output.view(-1, 1)






if __name__=="__main__":
    #test
    ngpu=1

    netG = cond_cnn_generator(ngpu=ngpu, nz=128, ngf=64, nc=1).cuda()
    netD = cond_cnn_discriminator(use_sigmoid = True, ngpu=ngpu, nc=1, ndf=64).cuda()

    z = torch.randn(5, 128,1,1).cuda()
    labels = np.random.choice(np.arange(10),size=5,replace=True)
    labels = torch.from_numpy(labels).type(torch.float).cuda()
    x = netG(z,labels)
    o = netD(x,labels)
    print(x.size())
    print(o.size())
