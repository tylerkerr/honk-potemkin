from aitextgen import aitextgen

''' generate one batch of sample text '''

ai = aitextgen(model_folder="trained_model", to_gpu=True)

ai.generate(n=5,
                max_length=2048,
                temperature=1.3,
                # repetition_penalty=1.2,
                top_p=0.9)