import { Players, Workspace } from "@rbxts/services";
import { Character, CompoundEffectsContainer, CreateServer } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";
const server = CreateServer()
server.Start()
task.wait(3)

const effect = CompoundEffectsContainer.GetCompoundEffectFromConstructor(Stun)
const _test = CompoundEffectsContainer.GetCompoundEffectFromName("Stun")
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char !== undefined) {
        effect?.ApplyTo(tver_char, 15)
    }
}