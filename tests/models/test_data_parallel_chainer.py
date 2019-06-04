import unittest
from delira import get_backends


class TestDataParallel(unittest.TestCase):

    def setUp(self) -> None:
        if "CHAINER" in get_backends():
            import chainer
            import chainer.link
            import chainer.links
            import chainer.functions
            import chainer.optimizers
            from delira.models.chainer_parallel import DataParallelOptimizer, \
                DataParallel

            # creating a really simple model to test dataparallel behavior
            class SimpleModel(chainer.link.Chain):
                def __init__(self):
                    super(SimpleModel, self).__init__()

                    with self.init_scope():
                        self.dense_1 = chainer.links.Linear(3, 32)
                        self.dense_2 = chainer.links.Linear(32, 2)

                def forward(self, x):
                    return self.dense_2(
                        chainer.functions.relu(
                            self.dense_1(x)))

            self.model = DataParallel(SimpleModel(),
                                      devices=["@numpy", "@numpy"])

            self.optimizer = DataParallelOptimizer.from_optimizer_class(
                chainer.optimizers.Adam
            )
            self.optimizer.setup(self.model)

    @unittest.skipIf("CHAINER" not in get_backends(),
                     "No CHAINER Backend installed")
    def test_update(self):
        import numpy as np
        import chainer

        input_tensor = np.random.rand(10, 3).astype(np.float32)
        label_tensor = np.random.rand(10, 2).astype(np.float)

        model_copy = self.model.copy()

        preds = self.model(input_tensor)

        loss = chainer.functions.sum(preds - label_tensor)

        self.model.cleargrads()
        loss.backward()
        self.optimizer.update()

        # check if param was updated
        for orig_param, updated_param in zip(model_copy.params(),
                                             self.model.params()):

            self.assertFalse(np.array_equal(orig_param, updated_param))

        # check if all grads were cleared
        self.model.cleargrads()
        for module in self.model.modules:
            for updated_param in module.params():
                self.assertIsNone(updated_param.grad_var)

    # test with keyword arguments
    def test_keyword_arguments_different_batchsize(self):
        import numpy as np
        import chainer

        # test batchsize smaller than, equal to and greater than number devices
        for batchsize in [1, 2, 3]:
            with self.subTest(batchsize=batchsize):
                input_kwargs = {
                    "x": np.random.rand(batchsize, 3).astype(np.float32)
                }

                pred = self.model(**input_kwargs)
                self.assertTupleEqual(pred.shape,
                                      (batchsize, 2))
                self.assertEqual(chainer.get_device(pred.device),
                                 chainer.get_device("@numpy"))

    # test with positional arguments
    def test_positional_arguments(self):
        import numpy as np
        import chainer

        # test batchsize smaller than, equal to and greater than number devices
        for batchsize in [1, 2, 3]:
            with self.subTest(batchsize=batchsize):
                input_args = [
                    np.random.rand(batchsize, 3).astype(np.float32)
                ]

                pred = self.model(*input_args)
                self.assertTupleEqual(pred.shape,
                                      (batchsize, 2))

                self.assertEqual(chainer.get_device(pred.device),
                                 chainer.get_device("@numpy"))


if __name__ == '__main__':
    unittest.main()
