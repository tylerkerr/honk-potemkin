from aitextgen import aitextgen

if __name__ == '__main__':
    ai = aitextgen(tf_gpt2="355M", to_gpu=True, model_folder='trained_model', model="pytorch_model.bin")

    training_data = "parsed_discord.txt"

    ai.train(training_data,
            line_by_line=False,
            from_cache=False,
            num_steps=80000,
            generate_every=500,
            save_every=2000,
            save_gdrive=False,
            learning_rate=1e-3,
            fp16=False,
            batch_size=1, 
            )