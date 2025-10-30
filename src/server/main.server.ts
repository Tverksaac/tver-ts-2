import { effect } from "@rbxts/charm";
import { Players } from "@rbxts/services";
import { Character, CreateServer, GetCompoundEffectFromConstructor } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";
const server = CreateServer()
server.Start()
task.wait(3)
const stun_effect = GetCompoundEffectFromConstructor(Stun)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char !== undefined && stun_effect) {
        while (task.wait(0.1)) {
            stun_effect.ApplyTo(tver_char, 0.05)
        }
    }
}