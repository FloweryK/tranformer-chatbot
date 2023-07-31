import json
import sentencepiece as spm
import torch
from torch.utils.data import Dataset
from constant import *


class MovieCorpusDataset(Dataset):
    def __init__(self, path_data, n_vocab):
        super().__init__()

        # load and encode data
        self.data = {}
        self.vocab = None
        self.load_data(path_data)
        self.load_vocab(n_vocab)
        self.encode_data()

        # filter answers with no question
        self.ids = [value['id'] for value in self.data.values() if value['question_id']]
        self.len = len(self.ids)
    
    def load_data(self, path_data):
        with open(path_data, 'r', encoding='iso-8859-1') as f:
            for line in f:
                # load line as json
                obj = json.loads(line)

                # make converstaion data
                text = obj['text'].strip()
                answer_id = obj['id']
                question_id = obj['reply-to']

                self.data[answer_id] = {
                    'id': answer_id,
                    'text': [text],
                    'question_id': question_id,
                }

    def load_vocab(self, n_vocab):
        # train sentencepiece
        with open('tmp.txt', 'w', encoding='utf8') as f:
            for chat in self.data.values():
                f.write(' '.join(chat['text']) + '\n')
        
        spm.SentencePieceTrainer.train(
            input='tmp.txt',
            vocab_size=n_vocab,
            model_prefix='tmp',
            model_type='bpe',
            max_sentence_length=9999,
            pad_id=PAD,
            pad_piece='[PAD]',
            unk_id=UNK,
            unk_piece='[UNK]',
            bos_id=BOS,
            bos_piece='[BOS]',
            eos_id=EOS,
            eos_piece='[EOS]',
            user_defined_symbols=['[SEP]', '[CLS]', '[MASK]']
        )

        # load vocab
        self.vocab = spm.SentencePieceProcessor()
        self.vocab.Load('tmp.model')
    
    def encode_data(self):
        # encode
        for chat_id in self.data:
            text = self.data[chat_id]['text']
            text_encode = [BOS]
            for t in text:
                text_encode.extend(self.vocab.EncodeAsIds(t) + [SEP])
            text_encode[-1] = EOS
            self.data[chat_id]['text_encode'] = text_encode
                
    def __len__(self):
        return self.len

    def __getitem__(self, index):
        answer_id = self.ids[index]
        answer = self.data[answer_id]

        question_id = answer['question_id']
        question = self.data[question_id]

        return (
            torch.tensor(question['text_encode']),
            torch.tensor(answer['text_encode']),
        )
