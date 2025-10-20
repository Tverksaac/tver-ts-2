import { Players} from "@rbxts/services";
import { Character, CompoundEffectsContainer, CreateServer } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";
const server = CreateServer()
server.Start()
task.wait(3)
const stun_effect = CompoundEffectsContainer.GetCompoundEffectFromConstructor(Stun)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    print("Unyielded!")
    if (tver_char !== undefined) {
        task.wait(1)
        stun_effect?.ApplyTo(tver_char, 1)
    }
}