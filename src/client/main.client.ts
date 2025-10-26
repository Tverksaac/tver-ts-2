import { ReplicatedStorage } from "@rbxts/services";
import { Character, CreateClient, GetCompoundEffectFromConstructor } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";

const client = CreateClient()
client.Start()

print(GetCompoundEffectFromConstructor(Stun))
