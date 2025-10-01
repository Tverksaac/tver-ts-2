import { Character, CreateClient } from "shared/tver/exports";

const client = CreateClient()
client.Start()

task.wait(8)

print(Character.GetAllCharactersArray())