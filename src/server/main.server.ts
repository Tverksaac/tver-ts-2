import { effect } from "@rbxts/charm";
import { Players } from "@rbxts/services";
import { Character, Container_CompoundEffect, CreateServer } from "shared/tver/exports";
import { SpeedBoost, Stun } from "shared/tver/test/compound_effects_classes";
const server = CreateServer()
server.Start()
task.wait(2)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char !== undefined) {
        new SpeedBoost(2).ApplyTo(tver_char, 10).Start()
    }
    
}