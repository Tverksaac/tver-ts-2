import { get_logger, is_client_context } from "shared/tver/utility/utils"

export abstract class Node {
    public Type = is_client_context()? "Client" : "Server"
    public Active = false
    public log = get_logger("[" + this.Type.upper() + "]")

    private readonly _registered: ModuleScript[] = []

    constructor () {}

    public Register(ToLoad: Folder | ModuleScript) {
        if (this.Active) {
            this.log.w(`Cannot register after ${this.Type} was activated`)
            return
        }

        if (ToLoad.IsA("ModuleScript")) {
            this._registered.push(ToLoad)
        } else if (ToLoad.IsA("Folder")) {
            ToLoad.GetDescendants().forEach((instance) => {
                if (instance.IsA("ModuleScript")) {
                    this._registered.push(instance)
                }
            })
        } else {
            this.log.w(`Cannot register ${ToLoad}: invalid type`)
        }
    }

    public Load() {
        if (this.Active) {
            this.log.w(`${this.Type} cannot be loaded after activation!`)
            return
        }

        const failed: ModuleScript[] = []

        this._registered.forEach((module) => {
            const [success, result] = pcall(() => {
                require(module)
            })
            if (!success) {
                this.log.e(`${module.Name} experienced error while loading: ${tostring(result)}`)
                failed.push(module)
            }
        })

        if (failed.size() > 0) {
            this.log.w(`${failed.size()} module(s) failed to load`)
        }
    }
}