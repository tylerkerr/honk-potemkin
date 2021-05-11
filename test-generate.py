from aitextgen import aitextgen

''' generate one batch of sample text '''

ai = aitextgen(model_folder="trained_model", to_gpu=True)

ai.generate(n=20,
            batch_size=50,
            max_length=256,
            temperature=0.8,
            top_p=0.9)