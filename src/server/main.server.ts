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
        const applied = stun_effect?.ApplyTo(tver_char, 3)
        stun_effect?.ApplyTo(tver_char, 10)
        task.wait(2)
        print('pausing')
        applied.Pause()
        task.wait(3)
        print('resuming')
        applied.Resume()
        task.wait(1)
        applied.End()
    }
}