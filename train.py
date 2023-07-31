import argparse
import sentencepiece as spm
import torch
from torch.utils.data import DataLoader, random_split
from torch.utils.tensorboard import SummaryWriter

import config
from constant import *
from dataset.movie_corpus_dataset import MovieCorpusDataset
from dataset.kakaotalk import KakaotalkDataset
from dataset.kakaotalk_mobile import KakaotalkMobileDataset
from dataset.korean_qa_dataset import KoreanQADataset
from model.classifier import Classifier
from trainer import Trainer


def collate_fn(inputs):
    x_enc, x_dec = list(zip(*inputs))

    x_enc = torch.nn.utils.rnn.pad_sequence(x_enc, batch_first=True, padding_value=PAD)
    x_dec = torch.nn.utils.rnn.pad_sequence(x_dec, batch_first=True, padding_value=PAD)
    
    return [x_enc, x_dec]


def get_model_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


class AdamWarmup:
    def __init__(self, optimizer, model_size, warmup_steps):
        self.optimizer = optimizer
        self.model_size = model_size
        self.warmup_steps = warmup_steps
        self.current_step = 0
        self.lr = 0
    
    def zero_grad(self):
        self.optimizer.zero_grad()
        
    def get_lr(self):
        return self.model_size ** (-0.5) * min(self.current_step ** (-0.5), self.current_step * self.warmup_steps ** (-1.5))
        
    def step(self):
        # Increment the number of steps each time we call the step function
        self.current_step += 1
        lr = self.get_lr()
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr

        # update the learning rate
        self.lr = lr
        self.optimizer.step()   


if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--data', required=True)
    args = parser.parse_args()

    # paths
    path_data = args.data

    # dataset
    dataset = MovieCorpusDataset(path_data, config.n_vocab)
    train_size = int(config.r_split * len(dataset))
    trainset, testset = random_split(dataset, [train_size, len(dataset) - train_size])

    # dataloader
    trainloader = DataLoader(trainset, batch_size=config.n_batch, shuffle=True, collate_fn=collate_fn)
    testloader = DataLoader(testset, batch_size=config.n_batch, shuffle=True, collate_fn=collate_fn)

    # model
    model = Classifier(config)
    model = model.to(config.device)
    print("model parameters:", get_model_parameters(model))

    # criterion and optimizer
    criterion = torch.nn.CrossEntropyLoss(ignore_index=PAD, label_smoothing=config.label_smoothing)
    adam = torch.optim.Adam(model.parameters(), lr=config.lr, betas=(0.9, 0.98), eps=1e-9)
    optimizer = AdamWarmup(adam, config.d_emb, config.warmup_steps)
    writer = SummaryWriter()

    # trainer
    trainer = Trainer(model, criterion, optimizer, writer)

    # train
    for epoch in range(config.n_epoch):
        trainer.run_epoch(epoch, trainloader, device=config.device, train=True, n_accum=config.n_accum)
        trainer.run_epoch(epoch, testloader, device=config.device, train=False, n_accum=config.n_accum)