from typing import Iterator, Sequence, Text, Tuple, Union
from scipy.sparse import vstack, coo_matrix
import numpy as np
from scipy.sparse import spmatrix
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression

NDArray = Union[np.ndarray, spmatrix]
TokenSeq = Sequence[Text]
PosSeq = Sequence[Text]


def read_ptbtagged(ptbtagged_path: str) -> Iterator[Tuple[TokenSeq, PosSeq]]:
    """Reads sentences from a Penn TreeBank .tagged file.
    Each sentence is a sequence of tokens and part-of-speech tags.

    Penn TreeBank .tagged files contain one token per line, with an empty line
    marking the end of each sentence. Each line is composed of a token, a tab
    character, and a part-of-speech tag. Here is an example:

        What	WP
        's	VBZ
        next	JJ
        ?	.

        Slides	NNS
        to	TO
        illustrate	VB
        Shostakovich	NNP
        quartets	NNS
        ?	.

    :param ptbtagged_path: The path of a Penn TreeBank .tagged file, formatted
    as above.
    :return: An iterator over sentences, where each sentence is a tuple of
    a sequence of tokens and a corresponding sequence of part-of-speech tags.
    """

    with open(ptbtagged_path) as infile:
        tok = []
        pos = []
        for line in infile:
            line = line.strip()
            if not line:
                yield (tok, pos)
                tok = []
                pos = []
                continue
            line = line.split("\t")
            tok.append(line[0])
            pos.append(line[1])
        yield (tok, pos)



class Classifier(object):
    def __init__(self):
        """Initializes the classifier."""
        self.lg = LogisticRegression(solver = "liblinear", penalty = "l1", C = 1.5, multi_class = "auto")

    def train(self, tagged_sentences: Iterator[Tuple[TokenSeq, PosSeq]]) -> Tuple[NDArray, NDArray]:
        """Trains the classifier on the part-of-speech tagged sentences,
        and returns the feature matrix and label vector on which it was trained.

        The feature matrix should have one row per training token. The number
        of columns is up to the implementation, but there must at least be 1
        feature for each token, named "token=T", where "T" is the token string,
        and one feature for the part-of-speech tag of the preceding token,
        named "pos-1=P", where "P" is the part-of-speech tag string, or "<s>" if
        the token was the first in the sentence. For example, if the input is:

            What	WP
            's	VBZ
            next	JJ
            ?	.

        Then the first row in the feature matrix should have features for
        "token=What" and "pos-1=<s>", the second row in the feature matrix
        should have features for "token='s" and "pos-1=WP", etc. The alignment
        between these feature names and the integer columns of the feature
        matrix is given by the `feature_index` method below.

        The label vector should have one entry per training token, and each
        entry should be an integer. The alignment between part-of-speech tag
        strings and the integers in the label vector is given by the
        `label_index` method below.

        :param tagged_sentences: An iterator over sentences, where each sentence
        is a tuple of a sequence of tokens and a corresponding sequence of
        part-of-speech tags.
        :return: A tuple of (feature-matrix, label-vector).
        """

        self.dv = DictVectorizer()
        self.le = LabelEncoder()
        whole_doc = []
        label = []
        for tok, pos in tagged_sentences:
            label += pos
            pos.insert(0, "<s>")
            tok = [("token=" + x) for x in tok]
            pos = [("pos-1=" + x) for x in pos]
            word_list = list(zip(tok, pos))
            for word in word_list:
                feature_count = {feature: word.count(feature) for feature in word}
                whole_doc.append(feature_count)
            
        self.dv.fit(whole_doc)
        self.le.fit(label)
        
        feature_matrix = self.dv.transform(whole_doc)
        label_matrix = self.le.transform(label)

        self.lg.fit(feature_matrix, label_matrix)

        return (feature_matrix, label_matrix)

    def feature_index(self, feature: Text) -> int:
        """Returns the column index corresponding to the given named feature.

        The `train` method should always be called before this method is called.

        :param feature: The string name of a feature.
        :return: The column index of the feature in the feature matrix returned
        by the `train` method.
        """
        return self.dv.vocabulary_[feature]

    def label_index(self, label: Text) -> int:
        """Returns the integer corresponding to the given part-of-speech tag

        The `train` method should always be called before this method is called.

        :param label: The part-of-speech tag string.
        :return: The integer for the part-of-speech tag, to be used in the label
        vector returned by the `train` method.
        """
        return self.le.transform([label])[0]

    def predict(self, tokens: TokenSeq) -> PosSeq:
        """Predicts part-of-speech tags for the sequence of tokens.

        This method delegates to either `predict_greedy` or `predict_viterbi`.
        The implementer may decide which one to delegate to.

        :param tokens: A sequence of tokens representing a sentence.
        :return: A sequence of part-of-speech tags, one for each token.
        """
        _, pos_tags = self.predict_greedy(tokens)
        # _, _, pos_tags = self.predict_viterbi(tokens)
        return pos_tags

    def predict_greedy(self, tokens: TokenSeq) -> Tuple[NDArray, PosSeq]:
        """Predicts part-of-speech tags for the sequence of tokens using a
        greedy algorithm, and returns the feature matrix and predicted tags.

        Each part-of-speech tag is predicted one at a time, and each prediction
        is considered a hard decision, that is, when predicting the
        part-of-speech tag for token i, the model will assume that its
        prediction for token i-1 is correct and unchangeable.

        The feature matrix should have one row per input token, and be formatted
        in the same way as the feature matrix in `train`.

        :param tokens: A sequence of tokens representing a sentence.
        :return: The feature matrix and the sequence of predicted part-of-speech
        tags (one for each input token).
        """

        label = "<s>"
        feature_list = []
        label_list = []
        for word in tokens:
            token = "token=" + word
            pos = "pos-1=" + label
            word_list = {token: 1, pos: 1}
            feature = self.dv.transform(word_list)
            label_num = self.lg.predict(feature)
            label = self.le.inverse_transform(label_num)[0]
            feature_list.append(coo_matrix(feature))
            label_list.append(label)
        feature_matrix = vstack(feature_list).toarray()

        return (feature_matrix, label_list)

    def predict_viterbi(self, tokens: TokenSeq) -> Tuple[NDArray, NDArray, PosSeq]:
        """Predicts part-of-speech tags for the sequence of tokens using the
        Viterbi algorithm, and returns the transition probability tensor,
        the Viterbi lattice, and the predicted tags.

        The entry i,j,k in the transition probability tensor should correspond
        to the log-probability estimated by the classifier of token i having
        part-of-speech tag k, given that the previous part-of-speech tag was j.
        Thus, the first dimension should match the number of tokens, the second
        dimension should be one more than the number of part of speech tags (the
        last entry in this dimension corresponds to "<s>"), and the third
        dimension should match the number of part-of-speech tags.

        The entry i,k in the Viterbi lattice should correspond to the maximum
        log-probability achievable via any path from token 0 to token i and
        ending at assigning token i the part-of-speech tag k.

        The predicted part-of-speech tags should correspond to the highest
        probability path through the lattice.

        :param tokens: A sequence of tokens representing a sentence.
        :return: The transition probability tensor, the Viterbi lattice, and the
        sequence of predicted part-of-speech tags (one for each input token).
        """
