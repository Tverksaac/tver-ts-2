import { effect } from "@rbxts/charm";
import { Players } from "@rbxts/services";
import { Character, Container_CompoundEffect, CreateServer } from "shared/tver/exports"
import { JumpBoost } from "shared/tver/test/compound_effects_classes";
const server = CreateServer()
server.Start()
task.wait(2)
const jumpboost = new JumpBoost(10)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char !== undefined) {
        const applied = jumpboost.ApplyTo(tver_char, 5).Start().Pause()
        print(tver_char)
    }
    
}