import { app } from "../../scripts/app.js";

async function exportWorkflow() {
    console.log("Exporting")

    let workflowName = window.document.title.split(" - ").slice(0, -1).join(" - ").trim();
    if(workflowName.startsWith("*")) workflowName = workflowName.slice(1)

    const result = await app.extensionManager.dialog.prompt({
        title: "Name",
        message: "Enter Workflow Name",
        defaultValue: workflowName
    });

    if(result == null) return;
    
    console.log(`Input: ${result}`);
    const { output } = await app.graphToPrompt();
    const response = await fetch(`/cozygen/workflows/${result}.json`, {
        method: "POST",
        body: JSON.stringify(output)
    });
    if (!response.ok) {
        app.extensionManager.toast.add({
            severity: "error",
            summary: "Error",
            detail: "Failed to process request",
            life: 5000
        });
    } else {
        app.extensionManager.toast.add({
            severity: "success",
            summary: "Success",
            detail: "Saved to " + (await response.json()).filename,
            life: 5000
        });
    }
}

app.registerExtension({
	name: "CozyGen.Export",
    commands: [{ 
        id: "exportWorkflow", 
        label: "Export To CozyGen", 
        function: exportWorkflow
    }],
    menuCommands: [
        // Add to File menu
        { 
            path: ["File"], 
            commands: ["exportWorkflow"] 
        }
    ]
});