import { effect } from "@rbxts/charm";
import { Players } from "@rbxts/services";
import { Character, Container_CompoundEffect, CreateServer } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";
const server = CreateServer()
server.Start()
task.wait(3)
const stun_effect = Container_CompoundEffect.GetFromConstructor(Stun)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char !== undefined && stun_effect) {
        tver_char.onReplicationReady(() => {
            stun_effect.ApplyTo(tver_char, 1)
            stun_effect.ApplyTo(tver_char, 2)
        })
    }
}