import { Players } from "@rbxts/services";
import { Character, CreateServer } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";
import { CharacterInstance } from "shared/tver/utility/_ts_only/interfaces";
import { log } from "shared/tver/utility/utils";

const server = CreateServer()
server.Start()
task.wait(3)

const effect = new Stun(5)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char) {
        effect.ApplyTo(tver_char)
    }
}
