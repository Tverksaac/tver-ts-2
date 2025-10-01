import { Players } from "@rbxts/services";
import { Character, CreateServer } from "shared/tver/exports";
import { CharacterInstance } from "shared/tver/utility/_ts_only/interfaces";

const server = CreateServer()
server.Start()
task.wait(5)
const plr = Players.GetPlayers()[1]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined

    if (tver_char) {
    }
}